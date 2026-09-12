import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from failure_transparent_agents.six_model_release import (
    EXPECTED_CONDITIONS,
    EXPECTED_DISPOSITIONS,
    EXPECTED_MODELS,
    SIX_MODEL_ARTIFACTS,
    build_six_model_results_bundle,
)


class SixModelReleaseTest(unittest.TestCase):
    def test_builds_deterministic_sanitized_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            analysis = Path(directory) / "analysis"
            output = Path(directory) / "dist"
            (root / "paper").mkdir(parents=True)
            (root / "data").mkdir(parents=True)
            (root / "paper" / "main.tex").write_text(
                "The unified results are not human-validated.\n",
                encoding="utf-8",
            )
            for relative in (
                "model_extension_manifest.json",
                "model_extension_summary.json",
                "model_extension_verification.json",
                "model_extension_span_audit.json",
            ):
                (root / "data" / relative).write_text(
                    '{"schema_version": "1.0"}\n',
                    encoding="utf-8",
                )
            for relative in SIX_MODEL_ARTIFACTS:
                path = analysis / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture\n", encoding="utf-8")

            rows = []
            response_index = 0
            for model, model_count in EXPECTED_MODELS.items():
                per_condition = model_count // len(EXPECTED_CONDITIONS)
                for condition in EXPECTED_CONDITIONS:
                    for repeat in range(per_condition):
                        response_id = f"resp_{response_index:04d}"
                        response_index += 1
                        rows.append(
                            {
                                "schema_version": "1.0",
                                "response_id": response_id,
                                "run_id": (
                                    "confirmatory-20260910-v1"
                                    if response_index <= 1800
                                    else "model-extension-20260912-v1"
                                ),
                                "scenario_id": f"scenario-{repeat}",
                                "base_task_id": f"task-{repeat % 100}",
                                "category": "web_unavailable",
                                "task_domain": "fixture",
                                "pressure_type": "neutral",
                                "difficulty": "low",
                                "condition": condition,
                                "repeat_index": repeat % 2,
                                "prompt_version": "fixture",
                                "provider": "fixture",
                                "model": model,
                                "response": "The tool failed.",
                                "status": "success",
                                "usage": {
                                    "input_tokens": 10,
                                    "cached_input_tokens": 0,
                                    "reasoning_tokens": 0,
                                    "output_tokens": 4,
                                    "estimated_cost_usd": 0.0,
                                    "latency_ms": 1,
                                    "resolved_model": model,
                                    "attempts": 1,
                                    "provider_request_id": "private-request-id",
                                    "attempt_errors": ["private retry detail"],
                                },
                                "label_annotator_id": "fixture-judge",
                                "label_annotator_type": "model",
                                "label_confidence": 3,
                                "label_evidence_spans": {
                                    outcome: []
                                    for outcome in (
                                        "false_success",
                                        "fabricated_details",
                                        "limitation_disclosed",
                                        "recovery_action",
                                        "useful_response",
                                        "over_refusal",
                                    )
                                },
                                "label_notes": "Fixture label.",
                                "false_success": False,
                                "fabricated_details": False,
                                "limitation_disclosed": True,
                                "recovery_action": True,
                                "useful_response": True,
                                "over_refusal": False,
                            }
                        )
            (analysis / "labeled_results.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows),
                encoding="utf-8",
            )

            approval = {
                "schema_version": "1.0",
                "status": "approved",
                "approved_by": "Test Author",
                "approved_at": "2026-09-12T06:30:00Z",
                "version_tag": "v0.3.0",
                "release_mode": "six_model_model_judge_only",
                "human_validation_status": "not_conducted",
                "six_model_release_authorized": True,
                "github_release_authorized": True,
                "raw_request_ids_disposition": "removed",
                "provider_output_dispositions": {
                    key: "approved_for_release"
                    for key in EXPECTED_DISPOSITIONS
                },
            }
            approval_path = root / "data" / "approval.json"
            approval_path.write_text(
                json.dumps(approval),
                encoding="utf-8",
            )

            with patch(
                "failure_transparent_agents.six_model_release.audit_release",
                return_value={"errors": [], "version": "0.3.0"},
            ):
                first = build_six_model_results_bundle(
                    source_root=root,
                    analysis_root=analysis,
                    approval_path=approval_path,
                    output_dir=output,
                )
                second = build_six_model_results_bundle(
                    source_root=root,
                    analysis_root=analysis,
                    approval_path=approval_path,
                    output_dir=output / "second",
                )
            self.assertEqual(
                first["archive_sha256"],
                second["archive_sha256"],
            )
            self.assertEqual(3600, first["public_labeled_responses"])
            with zipfile.ZipFile(first["archive"]) as archive:
                content = b"\n".join(
                    archive.read(name)
                    for name in archive.namelist()
                    if not name.endswith("/")
                )
                self.assertNotIn(b"provider_request_id", content)
                self.assertNotIn(b"private-request-id", content)
                self.assertNotIn(b"attempt_errors", content)
                self.assertNotIn(b"private retry detail", content)
                manifest_name = next(
                    name
                    for name in archive.namelist()
                    if name.endswith("/publication-manifest.json")
                )
                manifest = json.loads(archive.read(manifest_name))
                self.assertEqual(
                    3600,
                    manifest["public_labeled_responses"],
                )
                self.assertFalse(manifest["human_annotations_included"])


if __name__ == "__main__":
    unittest.main()
