"""Create an auditable author-signoff record for confirmatory collection."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

from .execution import file_sha256
from .model_verification import validate_model_verification
from .schema import load_scenarios


FREEZE_STATEMENT = (
    "I reviewed the benchmark, hypotheses, annotation rubric, prompts, exact "
    "model and region choices, judge, authorship, license, exclusions, "
    "analysis plan, and budget caps and authorize confirmatory data collection "
    "against the recorded hashes."
)
APPROVAL_SCHEMA_VERSION = "1.0"
APPROVAL_FIELDS = {
    "schema_version",
    "status",
    "approved_by",
    "approved_at",
    "authors",
    "license",
    "data_collection_authorized",
    "provider_arms",
    "judge_arms",
    "primary_budget_cap_usd",
    "judge_budget_cap_usd",
    "aggregate_budget_cap_usd",
}
APPROVAL_ARM_FIELDS = {
    "config",
    "provider",
    "model",
    "region",
    "max_budget_usd",
}


def freeze_confirmatory_manifest(
    *,
    manifest_path: str | Path,
    signer: str,
    protocol_path: str | Path,
    annotation_guide_path: str | Path,
    judge_prompt_path: str | Path,
    prompt_source_path: str | Path,
    provider_config_paths: Sequence[str | Path],
    judge_config_paths: Sequence[str | Path],
    source_paths: Sequence[str | Path],
    approval_path: str | Path,
    model_verification_path: str | Path | None = None,
) -> dict[str, Any]:
    if not signer.strip():
        raise ValueError("signer must be non-empty")
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("confirmatory manifest must be an object")
    if manifest.get("frozen"):
        raise ValueError("confirmatory manifest is already frozen")
    dataset_path = Path(str(manifest["dataset"]))
    if file_sha256(dataset_path) != manifest.get("dataset_sha256"):
        raise ValueError("dataset hash does not match the candidate manifest")
    scenarios = load_scenarios(dataset_path)
    if len(scenarios) != manifest.get("scenario_count"):
        raise ValueError("dataset count does not match the candidate manifest")
    if not provider_config_paths:
        raise ValueError("provider configs are required")
    if not judge_config_paths:
        raise ValueError("at least one judge config is required")
    if not source_paths:
        raise ValueError("scientific source files are required")
    approval = validate_collection_approval(
        approval_path,
        signer=signer,
        provider_config_paths=provider_config_paths,
        judge_config_paths=judge_config_paths,
    )
    model_verification = None
    if model_verification_path is not None:
        model_verification = validate_model_verification(
            model_verification_path,
            provider_config_paths=provider_config_paths,
            judge_config_paths=judge_config_paths,
        )

    frozen_values: dict[str, Any] = {
            "frozen": True,
            "requires_author_signoff": False,
            "frozen_at": datetime.now(timezone.utc).isoformat(),
            "signed_by": signer.strip(),
            "signoff_statement": FREEZE_STATEMENT,
            "collection_approval_path": str(Path(approval_path)),
            "collection_approval_sha256": file_sha256(approval_path),
            "collection_approval": approval,
            "protocol_sha256": file_sha256(protocol_path),
            "annotation_guide_sha256": file_sha256(annotation_guide_path),
            "judge_prompt_sha256": file_sha256(judge_prompt_path),
            "prompt_source_sha256": file_sha256(prompt_source_path),
            "provider_config_sha256s": {
                str(Path(config)): file_sha256(config)
                for config in sorted(provider_config_paths, key=str)
            },
            "judge_config_sha256s": {
                str(Path(config)): file_sha256(config)
                for config in sorted(judge_config_paths, key=str)
            },
            "source_sha256s": {
                str(Path(source)): file_sha256(source)
                for source in sorted(source_paths, key=str)
            },
        }
    if model_verification is not None:
        frozen_values.update(
            {
                "model_verification_path": str(Path(model_verification_path)),
                "model_verification_sha256": file_sha256(
                    model_verification_path
                ),
                "model_verification": model_verification,
            }
        )
    manifest.update(frozen_values)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return manifest


def verify_frozen_config(
    manifest: dict[str, Any],
    *,
    config_path: str | Path,
    config_group: str = "provider_config_sha256s",
) -> None:
    if not manifest.get("frozen"):
        raise ValueError("confirmatory manifest is not frozen")
    hashes = manifest.get(config_group)
    if not isinstance(hashes, dict):
        raise ValueError(f"frozen manifest lacks {config_group}")
    requested = Path(config_path)
    path = str(requested)
    expected = hashes.get(path)
    if expected is None:
        requested_resolved = requested.resolve()
        for frozen_path, frozen_hash in hashes.items():
            if Path(frozen_path).resolve() == requested_resolved:
                expected = frozen_hash
                break
    if not isinstance(expected, str):
        raise ValueError(f"{path} is not included in the frozen manifest")
    if file_sha256(path) != expected:
        raise ValueError(f"{path} changed after author signoff")


def verify_frozen_sources(manifest: dict[str, Any]) -> None:
    hashes = manifest.get("source_sha256s")
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError("frozen manifest lacks scientific source hashes")
    for raw_path, expected in hashes.items():
        if not isinstance(raw_path, str) or not isinstance(expected, str):
            raise ValueError("frozen source hash map is invalid")
        if file_sha256(raw_path) != expected:
            raise ValueError(f"{raw_path} changed after author signoff")
    approval_path = manifest.get("collection_approval_path")
    approval_sha256 = manifest.get("collection_approval_sha256")
    if not isinstance(approval_path, str) or not isinstance(
        approval_sha256,
        str,
    ):
        raise ValueError("frozen manifest lacks collection approval hash")
    if file_sha256(approval_path) != approval_sha256:
        raise ValueError("collection approval changed after author signoff")
    model_verification_path = manifest.get("model_verification_path")
    model_verification_sha256 = manifest.get("model_verification_sha256")
    if model_verification_path is not None or model_verification_sha256 is not None:
        if not isinstance(model_verification_path, str) or not isinstance(
            model_verification_sha256,
            str,
        ):
            raise ValueError("frozen manifest has invalid model verification hash")
        if file_sha256(model_verification_path) != model_verification_sha256:
            raise ValueError("model verification changed after author signoff")


def validate_collection_approval(
    approval_path: str | Path,
    *,
    signer: str,
    provider_config_paths: Sequence[str | Path],
    judge_config_paths: Sequence[str | Path],
) -> dict[str, Any]:
    """Validate explicit authorship, model, region, and budget authorization."""

    path = Path(approval_path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"collection approval file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError("collection approval must contain valid JSON") from error
    if not isinstance(value, dict):
        raise ValueError("collection approval must be an object")
    _require_exact_fields(value, APPROVAL_FIELDS, "collection approval")
    if value["schema_version"] != APPROVAL_SCHEMA_VERSION:
        raise ValueError(
            "unsupported collection approval schema_version "
            f"{value['schema_version']!r}"
        )
    if value["status"] != "approved":
        raise ValueError("collection approval status must be 'approved'")
    approved_by = _nonempty_string(value["approved_by"], "approved_by")
    if approved_by != signer.strip():
        raise ValueError("collection approval approved_by must match signer")
    _aware_iso8601(value["approved_at"], "approved_at")
    if value["data_collection_authorized"] is not True:
        raise ValueError("data_collection_authorized must be true")
    authors = value["authors"]
    if (
        not isinstance(authors, list)
        or not authors
        or any(not isinstance(author, str) or not author.strip() for author in authors)
    ):
        raise ValueError("authors must be a non-empty array of names")
    normalized_authors = [author.strip() for author in authors]
    if len(set(normalized_authors)) != len(normalized_authors):
        raise ValueError("authors must not contain duplicates")
    if signer.strip() not in normalized_authors:
        raise ValueError("signer must be included in authors")
    if value["license"] != "MIT":
        raise ValueError("collection approval license must be 'MIT'")

    provider_arms = _validate_approval_arms(
        value["provider_arms"],
        provider_config_paths,
        "provider_arms",
    )
    judge_arms = _validate_approval_arms(
        value["judge_arms"],
        judge_config_paths,
        "judge_arms",
    )
    primary_cap = sum(float(arm["max_budget_usd"]) for arm in provider_arms)
    judge_cap = sum(float(arm["max_budget_usd"]) for arm in judge_arms)
    _require_equal_budget(
        value["primary_budget_cap_usd"],
        primary_cap,
        "primary_budget_cap_usd",
    )
    _require_equal_budget(
        value["judge_budget_cap_usd"],
        judge_cap,
        "judge_budget_cap_usd",
    )
    _require_equal_budget(
        value["aggregate_budget_cap_usd"],
        primary_cap + judge_cap,
        "aggregate_budget_cap_usd",
    )
    return {
        **value,
        "approved_by": approved_by,
        "authors": normalized_authors,
        "provider_arms": provider_arms,
        "judge_arms": judge_arms,
        "primary_budget_cap_usd": primary_cap,
        "judge_budget_cap_usd": judge_cap,
        "aggregate_budget_cap_usd": primary_cap + judge_cap,
    }


def _validate_approval_arms(
    raw_arms: Any,
    config_paths: Sequence[str | Path],
    name: str,
) -> list[dict[str, Any]]:
    if not isinstance(raw_arms, list):
        raise ValueError(f"{name} must be an array")
    approved: dict[Path, dict[str, Any]] = {}
    for index, raw_arm in enumerate(raw_arms):
        if not isinstance(raw_arm, dict):
            raise ValueError(f"{name}[{index}] must be an object")
        _require_exact_fields(raw_arm, APPROVAL_ARM_FIELDS, f"{name}[{index}]")
        config = Path(_nonempty_string(raw_arm["config"], f"{name}[{index}].config"))
        resolved = config.resolve()
        if resolved in approved:
            raise ValueError(f"{name} contains duplicate config {config}")
        region = raw_arm["region"]
        if region is not None:
            region = _nonempty_string(region, f"{name}[{index}].region")
        approved[resolved] = {
            "config": str(config),
            "provider": _nonempty_string(
                raw_arm["provider"],
                f"{name}[{index}].provider",
            ),
            "model": _nonempty_string(raw_arm["model"], f"{name}[{index}].model"),
            "region": region,
            "max_budget_usd": _positive_number(
                raw_arm["max_budget_usd"],
                f"{name}[{index}].max_budget_usd",
            ),
        }

    expected = [_config_approval_arm(path) for path in config_paths]
    if len(approved) != len(expected):
        raise ValueError(f"{name} must approve every frozen config exactly once")
    normalized: list[dict[str, Any]] = []
    for expected_arm in expected:
        resolved = Path(expected_arm["config"]).resolve()
        actual = approved.get(resolved)
        if actual is None:
            raise ValueError(
                f"{name} does not approve config {expected_arm['config']}"
            )
        for field in ("provider", "model", "region"):
            if actual[field] != expected_arm[field]:
                raise ValueError(
                    f"{name} {expected_arm['config']} has incorrect {field}"
                )
        _require_equal_budget(
            actual["max_budget_usd"],
            float(expected_arm["max_budget_usd"]),
            f"{name} {expected_arm['config']} max_budget_usd",
        )
        normalized.append(actual)
    return sorted(normalized, key=lambda arm: arm["config"])


def _config_approval_arm(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"provider config {path} must be an object")
    provider = _nonempty_string(
        value.get("provider_name"),
        f"{path}.provider_name",
    )
    base_url = _nonempty_string(value.get("base_url"), f"{path}.base_url")
    return {
        "config": str(path),
        "provider": provider,
        "model": _nonempty_string(value.get("model"), f"{path}.model"),
        "region": _region_from_config(provider, base_url),
        "max_budget_usd": _positive_number(
            value.get("max_budget_usd"),
            f"{path}.max_budget_usd",
        ),
    }


def _region_from_config(provider: str, base_url: str) -> str | None:
    hostname = urlparse(base_url).hostname or ""
    for prefix, suffix in (
        ("bedrock-mantle.", ".api.aws"),
        ("bedrock-runtime.", ".amazonaws.com"),
    ):
        if hostname.startswith(prefix) and hostname.endswith(suffix):
            region = hostname[len(prefix) : -len(suffix)]
            if region:
                return region
    if provider == "nvidia-bedrock":
        raise ValueError("nvidia-bedrock base_url does not encode an AWS region")
    return None


def _require_exact_fields(
    value: dict[str, Any],
    expected: set[str],
    name: str,
) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise ValueError(f"{name} fields mismatch: missing={missing}, extra={extra}")


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _positive_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValueError(f"{name} must be a positive number")
    return float(value)


def _require_equal_budget(value: Any, expected: float, name: str) -> None:
    actual = _positive_number(value, name)
    if abs(actual - expected) > 1e-9:
        raise ValueError(f"{name} must equal the frozen config total ${expected:.2f}")


def _aware_iso8601(value: Any, name: str) -> datetime:
    text = _nonempty_string(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signer", required=True)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data/confirmatory_manifest.json"),
    )
    parser.add_argument(
        "--protocol",
        type=Path,
        default=Path("docs/research_protocol.md"),
    )
    parser.add_argument(
        "--annotation-guide",
        type=Path,
        default=Path("docs/annotation_guide.md"),
    )
    parser.add_argument(
        "--judge-prompt",
        type=Path,
        default=Path("docs/judge_prompt.md"),
    )
    parser.add_argument(
        "--prompt-source",
        type=Path,
        default=Path("src/failure_transparent_agents/conditions.py"),
    )
    parser.add_argument(
        "--provider-config",
        type=Path,
        action="append",
        dest="provider_configs",
    )
    parser.add_argument(
        "--judge-config",
        type=Path,
        action="append",
        dest="judge_configs",
    )
    parser.add_argument(
        "--approval",
        type=Path,
        default=Path("data/confirmatory_approval.json"),
    )
    parser.add_argument(
        "--model-verification",
        type=Path,
        default=Path("data/model_verification.json"),
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    provider_configs = args.provider_configs or sorted(
        Path("configs/providers").glob("*.json")
    )
    judge_configs = args.judge_configs or sorted(
        Path("configs/judges").glob("*.json")
    )
    source_paths = [
        *sorted(Path("src/failure_transparent_agents").glob("*.py")),
        Path("scripts/generate_confirmatory_dataset.py"),
        Path("CITATION.cff"),
        Path("LICENSE"),
    ]
    try:
        manifest = freeze_confirmatory_manifest(
            manifest_path=args.manifest,
            signer=args.signer,
            protocol_path=args.protocol,
            annotation_guide_path=args.annotation_guide,
            judge_prompt_path=args.judge_prompt,
            prompt_source_path=args.prompt_source,
            provider_config_paths=provider_configs,
            judge_config_paths=judge_configs,
            source_paths=source_paths,
            approval_path=args.approval,
            model_verification_path=args.model_verification,
        )
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
