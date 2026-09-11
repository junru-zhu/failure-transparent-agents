import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from failure_transparent_agents.full_scale_validation import (
    run_full_scale_validation,
)
from failure_transparent_agents.model_only_release import (
    build_model_only_results_bundle,
)
from failure_transparent_agents.publication_gate import (
    audit_final_publication,
)
from failure_transparent_agents.public_results import (
    build_public_results_bundle,
)
from failure_transparent_agents.sensitivity import run_human_sensitivity


ROOT = Path(__file__).parents[1]


class PublicationGateTest(unittest.TestCase):
    def test_requires_complete_human_results_and_explicit_approval(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "fixture"
            run_full_scale_validation(
                dataset_path=ROOT / "data" / "confirmatory_scenarios.jsonl",
                output_dir=output,
                bootstrap_repetitions=10,
                permutation_repetitions=20,
            )
            judge_dir = output / "judge"
            judge_dir.mkdir()
            shutil.copyfile(
                output / "model_judge_labels.jsonl",
                judge_dir / "model_judge_labels_complete.jsonl",
            )
            for arm, fixture_name in (
                ("openai", "fixture-openai"),
                ("anthropic", "fixture-anthropic"),
                ("nvidia", "fixture-nvidia"),
            ):
                arm_dir = output / "primary" / arm
                arm_dir.mkdir(parents=True)
                shutil.copyfile(
                    output / f"raw_{fixture_name}.jsonl",
                    arm_dir / "raw_results.jsonl",
                )
            shutil.copytree(
                output / "analysis",
                output / "analysis-model-judge",
            )

            model_only_source = Path(directory) / "model-only-source"
            (model_only_source / "paper").mkdir(parents=True)
            (model_only_source / "paper" / "main.tex").write_text(
                "These results are not human-validated.\n",
                encoding="utf-8",
            )
            model_only_approval_path = (
                Path(directory) / "model_only_publication_approval.json"
            )
            model_only_approval = {
                "schema_version": "1.0",
                "status": "approved",
                "approved_by": "Test Author",
                "approved_at": "2026-09-11T12:00:00-07:00",
                "version_tag": "v0.2.0",
                "release_mode": "model_judge_only",
                "human_validation_status": "not_conducted",
                "model_judge_only_release_authorized": True,
                "github_release_authorized": True,
                "raw_request_ids_disposition": "removed",
                "provider_output_dispositions": {
                    "openai_judge": "approved_for_release",
                    "openai_primary_bedrock": "approved_for_release",
                    "anthropic_bedrock": "approved_for_release",
                    "nvidia_bedrock": "approved_for_release",
                },
                "notes": "Synthetic model-judge-only test approval.",
            }
            model_only_approval_path.write_text(
                json.dumps(model_only_approval),
                encoding="utf-8",
            )
            with patch(
                "failure_transparent_agents.model_only_release.audit_release",
                return_value={"errors": [], "version": "0.2.0"},
            ):
                model_only_release = build_model_only_results_bundle(
                    source_root=model_only_source,
                    results_root=output,
                    approval_path=model_only_approval_path,
                    output_dir=Path(directory) / "dist-model-only",
                )
            self.assertEqual(
                1800,
                model_only_release["public_labeled_responses"],
            )
            with zipfile.ZipFile(model_only_release["archive"]) as archive:
                archive_names = archive.namelist()
                manifest_name = next(
                    name
                    for name in archive_names
                    if name.endswith("/publication-manifest.json")
                )
                manifest = json.loads(archive.read(manifest_name))
                self.assertEqual(
                    "model_judge_only_not_human_validated",
                    manifest["scientific_status"],
                )
                self.assertFalse(manifest["human_annotations_included"])
                self.assertEqual(
                    1800,
                    manifest["public_labeled_responses"],
                )
                labeled_name = next(
                    name
                    for name in archive_names
                    if name.endswith("/analysis/labeled_results.jsonl")
                )
                public_rows = [
                    json.loads(line)
                    for line in archive.read(labeled_name).splitlines()
                    if line
                ]
                self.assertEqual(1800, len(public_rows))
                self.assertTrue(
                    all(
                        row["model_judge_label"] is not None
                        and row["human_consensus_label"] is None
                        for row in public_rows
                    )
                )
                self.assertEqual(
                    [labeled_name],
                    [
                        name
                        for name in archive_names
                        if name.endswith(".jsonl")
                    ],
                )
                for name in archive_names:
                    self.assertNotIn(
                        b"provider_request_id",
                        archive.read(name),
                    )
                self.assertFalse(
                    any(
                        "human_sample_key" in name
                        or "/human/" in name
                        or "/human_validation/" in name
                        for name in archive_names
                    )
                )

            run_human_sensitivity(
                raw_paths=[
                    output / "raw_fixture-openai.jsonl",
                    output / "raw_fixture-anthropic.jsonl",
                    output / "raw_fixture-nvidia.jsonl",
                ],
                human_labels_path=output / "human" / "human_labels.jsonl",
                sample_key_path=(
                    output / "human" / "human_sample_key.jsonl"
                ),
                sample_manifest_path=(
                    output / "human" / "human_sample_manifest.json"
                ),
                model_judge_labels_path=output / "model_judge_labels.jsonl",
                output_dir=output / "analysis-human-sensitivity",
                bootstrap_repetitions=10,
                seed=20260910,
                expected_sample_size=270,
            )
            approval_path = Path(directory) / "publication_approval.json"
            approval = {
                "schema_version": "1.0",
                "status": "approved",
                "approved_by": "Test Author",
                "approved_at": "2026-09-11T12:00:00-07:00",
                "version_tag": "v0.2.0",
                "human_validation_reviewed": True,
                "github_release_authorized": True,
                "raw_request_ids_disposition": "removed",
                "provider_output_dispositions": {
                    "openai_judge": "approved_for_release",
                    "openai_primary_bedrock": "approved_for_release",
                    "anthropic_bedrock": "approved_for_release",
                    "nvidia_bedrock": "approved_for_release",
                },
                "notes": "Synthetic test approval.",
            }
            approval_path.write_text(
                json.dumps(approval),
                encoding="utf-8",
            )

            report = audit_final_publication(
                source_root=ROOT,
                results_root=output,
                first_labels_path=(
                    output / "human" / "human_labels_annotator_a.jsonl"
                ),
                second_labels_path=(
                    output / "human" / "human_labels_annotator_b.jsonl"
                ),
                approval_path=approval_path,
            )
            self.assertEqual([], report["errors"])
            self.assertEqual([], report["publication_blockers"])
            self.assertTrue(report["final_publication_ready"])
            self.assertEqual(1800, report["model_judge_labels"])
            self.assertEqual(
                1800,
                report["final_analysis_labeled_responses"],
            )

            release = build_public_results_bundle(
                source_root=ROOT,
                results_root=output,
                first_labels_path=(
                    output / "human" / "human_labels_annotator_a.jsonl"
                ),
                second_labels_path=(
                    output / "human" / "human_labels_annotator_b.jsonl"
                ),
                approval_path=approval_path,
                output_dir=Path(directory) / "dist",
            )
            self.assertEqual(1800, release["public_labeled_responses"])
            archive_path = Path(release["archive"])
            with zipfile.ZipFile(archive_path) as archive:
                labeled_name = next(
                    name
                    for name in archive.namelist()
                    if name.endswith("/analysis/labeled_results.jsonl")
                )
                labeled_content = archive.read(labeled_name)
                self.assertNotIn(b"provider_request_id", labeled_content)
            self.assertNotIn(b"fixture-request-", labeled_content)
            self.assertNotIn(b"human_sample_key", b"\n".join(
                name.encode("utf-8") for name in archive.namelist()
            ))

            approval["provider_output_dispositions"]["nvidia_bedrock"] = (
                "excluded_from_public_artifact"
            )
            approval_path.write_text(
                json.dumps(approval),
                encoding="utf-8",
            )
            excluded_release = build_public_results_bundle(
                source_root=ROOT,
                results_root=output,
                first_labels_path=(
                    output / "human" / "human_labels_annotator_a.jsonl"
                ),
                second_labels_path=(
                    output / "human" / "human_labels_annotator_b.jsonl"
                ),
                approval_path=approval_path,
                output_dir=Path(directory) / "dist-excluded",
            )
            self.assertEqual(
                1200,
                excluded_release["public_labeled_responses"],
            )
            self.assertEqual(
                ["nvidia"],
                excluded_release["excluded_primary_arms"],
            )

            approval["provider_output_dispositions"]["nvidia_bedrock"] = (
                "pending"
            )
            approval_path.write_text(
                json.dumps(approval),
                encoding="utf-8",
            )
            blocked = audit_final_publication(
                source_root=ROOT,
                results_root=output,
                first_labels_path=(
                    output / "human" / "human_labels_annotator_a.jsonl"
                ),
                second_labels_path=(
                    output / "human" / "human_labels_annotator_b.jsonl"
                ),
                approval_path=approval_path,
            )
            self.assertFalse(blocked["final_publication_ready"])
            self.assertTrue(
                any(
                    "nvidia_bedrock" in blocker
                    for blocker in blocked["publication_blockers"]
                )
            )


if __name__ == "__main__":
    unittest.main()
