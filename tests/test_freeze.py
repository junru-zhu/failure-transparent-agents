from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import urlparse

from failure_transparent_agents.freeze import (
    freeze_confirmatory_manifest,
    main as freeze_main,
    validate_collection_approval,
    verify_frozen_config,
    verify_frozen_sources,
)
from failure_transparent_agents.api_providers import load_provider_settings
from failure_transparent_agents.execution import file_sha256


ROOT = Path(__file__).parents[1]


class FreezeTest(unittest.TestCase):
    def test_records_and_verifies_config_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "manifest.json"
            candidate = _unfrozen_repository_manifest()
            candidate["dataset"] = str(
                ROOT / "data" / "confirmatory_scenarios.jsonl"
            )
            manifest_path.write_text(
                json.dumps(candidate),
                encoding="utf-8",
            )
            provider_config = (
                ROOT / "configs" / "providers" / "openai-gpt-5.6-terra.json"
            )
            judge_config = (
                ROOT / "configs" / "judges" / "openai-gpt-5.4-mini.json"
            )
            approval_path = Path(directory) / "approval.json"
            _write_approval(
                approval_path,
                signer="Test Author",
                provider_config=provider_config,
                judge_config=judge_config,
            )
            frozen = freeze_confirmatory_manifest(
                manifest_path=manifest_path,
                signer="Test Author",
                protocol_path=ROOT / "docs" / "research_protocol.md",
                annotation_guide_path=ROOT / "docs" / "annotation_guide.md",
                judge_prompt_path=ROOT / "docs" / "judge_prompt.md",
                prompt_source_path=(
                    ROOT
                    / "src"
                    / "failure_transparent_agents"
                    / "conditions.py"
                ),
                provider_config_paths=[provider_config],
                judge_config_paths=[judge_config],
                source_paths=[
                    ROOT / "src" / "failure_transparent_agents" / "conditions.py"
                ],
                approval_path=approval_path,
            )
            self.assertTrue(frozen["frozen"])
            self.assertEqual(
                "Test Author",
                frozen["collection_approval"]["approved_by"],
            )
            self.assertEqual(
                80.0,
                frozen["collection_approval"]["aggregate_budget_cap_usd"],
            )
            verify_frozen_config(frozen, config_path=provider_config)
            verify_frozen_sources(frozen)

            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            approval["status"] = "pending"
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            with self.assertRaisesRegex(
                ValueError,
                "collection approval changed",
            ):
                verify_frozen_sources(frozen)

    def test_rejects_pending_and_incorrect_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            approval_path = Path(directory) / "approval.json"
            provider_config = (
                ROOT / "configs" / "providers" / "openai-gpt-5.6-terra.json"
            )
            judge_config = (
                ROOT / "configs" / "judges" / "openai-gpt-5.4-mini.json"
            )
            _write_approval(
                approval_path,
                signer="Test Author",
                provider_config=provider_config,
                judge_config=judge_config,
            )
            approval = json.loads(approval_path.read_text(encoding="utf-8"))
            approval["status"] = "pending"
            approval["data_collection_authorized"] = False
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "status must be 'approved'"):
                validate_collection_approval(
                    approval_path,
                    signer="Test Author",
                    provider_config_paths=[provider_config],
                    judge_config_paths=[judge_config],
                )

            approval["status"] = "approved"
            approval["data_collection_authorized"] = True
            approval["provider_arms"][0]["model"] = "wrong-model"
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "incorrect model"):
                validate_collection_approval(
                    approval_path,
                    signer="Test Author",
                    provider_config_paths=[provider_config],
                    judge_config_paths=[judge_config],
                )

    def test_repository_approval_matches_all_configs(self) -> None:
        validated = validate_collection_approval(
            ROOT / "data" / "confirmatory_approval.json",
            signer="Junru Zhu",
            provider_config_paths=sorted(
                (ROOT / "configs" / "providers").glob("*.json")
            ),
            judge_config_paths=sorted(
                (ROOT / "configs" / "judges").glob("*.json")
            ),
        )
        self.assertEqual("approved", validated["status"])
        self.assertTrue(validated["data_collection_authorized"])
        self.assertEqual(120.0, validated["aggregate_budget_cap_usd"])
        self.assertEqual(
            "us-east-1",
            next(
                arm["region"]
                for arm in validated["provider_arms"]
                if arm["provider"] == "nvidia-bedrock"
            ),
        )

    def test_cli_cleanly_rejects_pending_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "manifest.json"
            manifest_path.write_text(
                json.dumps(_unfrozen_repository_manifest()),
                encoding="utf-8",
            )
            approval = json.loads(
                (
                    ROOT / "data" / "confirmatory_approval.json"
                ).read_text(encoding="utf-8")
            )
            approval["status"] = "pending"
            approval["approved_by"] = None
            approval["approved_at"] = None
            approval["data_collection_authorized"] = False
            approval_path = Path(directory) / "approval.json"
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as raised:
                    freeze_main(
                        [
                            "--signer",
                            "Junru Zhu",
                            "--manifest",
                            str(manifest_path),
                            "--approval",
                            str(approval_path),
                        ]
                    )
            self.assertEqual(2, raised.exception.code)
            self.assertIn(
                "collection approval status must be 'approved'",
                stderr.getvalue(),
            )
            self.assertNotIn("Traceback", stderr.getvalue())

    def test_freeze_hashes_model_verification_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest_path = Path(directory) / "manifest.json"
            candidate = _unfrozen_repository_manifest()
            candidate["dataset"] = str(
                ROOT / "data" / "confirmatory_scenarios.jsonl"
            )
            manifest_path.write_text(json.dumps(candidate), encoding="utf-8")
            provider_config = (
                ROOT / "configs" / "providers" / "openai-gpt-5.6-terra.json"
            )
            judge_config = (
                ROOT / "configs" / "judges" / "openai-gpt-5.4-mini.json"
            )
            approval_path = Path(directory) / "approval.json"
            _write_approval(
                approval_path,
                signer="Test Author",
                provider_config=provider_config,
                judge_config=judge_config,
            )
            verification_path = Path(directory) / "model-verification.json"
            _write_model_verification(
                verification_path,
                provider_config=provider_config,
                judge_config=judge_config,
            )

            frozen = freeze_confirmatory_manifest(
                manifest_path=manifest_path,
                signer="Test Author",
                protocol_path=ROOT / "docs" / "research_protocol.md",
                annotation_guide_path=ROOT / "docs" / "annotation_guide.md",
                judge_prompt_path=ROOT / "docs" / "judge_prompt.md",
                prompt_source_path=(
                    ROOT
                    / "src"
                    / "failure_transparent_agents"
                    / "conditions.py"
                ),
                provider_config_paths=[provider_config],
                judge_config_paths=[judge_config],
                source_paths=[
                    ROOT / "src" / "failure_transparent_agents" / "conditions.py"
                ],
                approval_path=approval_path,
                model_verification_path=verification_path,
            )
            self.assertEqual(
                file_sha256(verification_path),
                frozen["model_verification_sha256"],
            )
            verify_frozen_sources(frozen)

            verification = json.loads(
                verification_path.read_text(encoding="utf-8")
            )
            verification["verification_scope"] = "changed after signoff"
            verification_path.write_text(
                json.dumps(verification),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "model verification changed",
            ):
                verify_frozen_sources(frozen)


def _write_approval(
    path: Path,
    *,
    signer: str,
    provider_config: Path,
    judge_config: Path,
) -> None:
    provider = json.loads(provider_config.read_text(encoding="utf-8"))
    judge = json.loads(judge_config.read_text(encoding="utf-8"))
    provider_cap = float(provider["max_budget_usd"])
    judge_cap = float(judge["max_budget_usd"])
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "status": "approved",
                "approved_by": signer,
                "approved_at": "2026-09-10T13:00:00-07:00",
                "authors": [signer],
                "license": "MIT",
                "data_collection_authorized": True,
                "provider_arms": [
                    {
                        "config": str(provider_config),
                        "provider": provider["provider_name"],
                        "model": provider["model"],
                        "region": _config_region(provider),
                        "max_budget_usd": provider_cap,
                    }
                ],
                "judge_arms": [
                    {
                        "config": str(judge_config),
                        "provider": judge["provider_name"],
                        "model": judge["model"],
                        "region": None,
                        "max_budget_usd": judge_cap,
                    }
                ],
                "primary_budget_cap_usd": provider_cap,
                "judge_budget_cap_usd": judge_cap,
                "aggregate_budget_cap_usd": provider_cap + judge_cap,
            }
        ),
        encoding="utf-8",
    )


def _write_model_verification(
    path: Path,
    *,
    provider_config: Path,
    judge_config: Path,
) -> None:
    arms = []
    for role, config_path, source_url in (
        (
            "primary",
            provider_config,
            "https://developers.openai.com/api/docs/models/gpt-5.6-terra",
        ),
        (
            "judge",
            judge_config,
            "https://developers.openai.com/api/docs/models/gpt-5.4-mini",
        ),
    ):
        settings = load_provider_settings(str(config_path))
        arms.append(
            {
                "role": role,
                "config": str(config_path),
                "config_sha256": file_sha256(config_path),
                "provider": settings.provider_name,
                "model": settings.model,
                "region": _config_region(
                    json.loads(config_path.read_text(encoding="utf-8"))
                ),
                "provider_type": settings.provider_type,
                "pricing_usd_per_million_tokens": {
                    "input": settings.pricing.input_per_million,
                    "cached_input": settings.pricing.cached_input_per_million,
                    "output": settings.pricing.output_per_million,
                },
                "documented_pricing_usd_per_million_tokens": {
                    "input": settings.pricing.input_per_million,
                    "cached_input": settings.pricing.cached_input_per_million,
                    "output": settings.pricing.output_per_million,
                },
                "reservation_pricing_policy": "documented-current-rate",
                "parameter_constraints": {
                    "reasoning_effort": "none",
                    "temperature": "unset",
                },
                "sources": [
                    {
                        "url": source_url,
                        "claims": ["Model and pricing verified for test fixture."],
                    }
                ],
            }
        )
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "status": "verified",
                "verified_at": "2026-09-10T13:00:00-07:00",
                "verification_scope": "Test fixture verification.",
                "arms": arms,
            }
        ),
        encoding="utf-8",
    )


def _unfrozen_repository_manifest() -> dict[str, object]:
    manifest = json.loads(
        (ROOT / "data" / "confirmatory_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    candidate_fields = {
        "base_task_count",
        "benchmark",
        "candidate_version",
        "category_counts",
        "dataset",
        "dataset_sha256",
        "generator",
        "pressure_type_counts",
        "scenario_count",
        "schema_version",
    }
    candidate = {
        key: value for key, value in manifest.items() if key in candidate_fields
    }
    candidate["frozen"] = False
    candidate["requires_author_signoff"] = True
    return candidate


def _config_region(config: dict[str, object]) -> str | None:
    hostname = urlparse(str(config["base_url"])).hostname or ""
    prefix = "bedrock-runtime."
    suffix = ".amazonaws.com"
    if hostname.startswith(prefix) and hostname.endswith(suffix):
        return hostname[len(prefix) : -len(suffix)]
    return None


if __name__ == "__main__":
    unittest.main()
