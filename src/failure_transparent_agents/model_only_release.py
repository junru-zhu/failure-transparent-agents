"""Build a transparent model-judge-only results release."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence
import zipfile

from .analysis import load_raw_results
from .labels import load_labels
from .public_results import (
    PRIMARY_DISPOSITIONS,
    _copy_artifacts,
    _jsonl_bytes,
    _load_json_object,
    _public_labeled_record,
    _scan_public_payload,
    _zip_info,
)
from .release import (
    DEFAULT_SOURCE_DATE_EPOCH,
    audit_release,
    canonical_json,
    sha256_bytes,
    sha256_file,
)


MODEL_ONLY_ARTIFACTS = (
    "analysis_summary.json",
    "rates.csv",
    "comparisons.csv",
    "efficiency.csv",
    "figures/figure1_false_success_by_model.svg",
    "figures/figure2_transparency_and_utility.svg",
    "figures/figure3_pressure_ablation.svg",
    "tables/ablation_table.tex",
)


def build_model_only_results_bundle(
    *,
    source_root: str | Path,
    results_root: str | Path,
    approval_path: str | Path,
    output_dir: str | Path,
    source_date_epoch: int = DEFAULT_SOURCE_DATE_EPOCH,
) -> dict[str, Any]:
    root = Path(source_root)
    results = Path(results_root)
    approval = _load_json_object(approval_path)
    source_audit = audit_release(root)
    if source_audit["errors"]:
        raise ValueError(
            "source release audit failed: "
            + "; ".join(source_audit["errors"])
        )
    _validate_approval(approval, f"v{source_audit['version']}")
    paper = (root / "paper" / "main.tex").read_text(encoding="utf-8")
    if "not human-validated" not in paper:
        raise ValueError(
            "paper must explicitly state that results are not human-validated"
        )
    if source_date_epoch < DEFAULT_SOURCE_DATE_EPOCH:
        raise ValueError(
            f"source_date_epoch must be at least {DEFAULT_SOURCE_DATE_EPOCH}"
        )

    dispositions = approval["provider_output_dispositions"]
    included_arms = [
        arm
        for arm, disposition_key in PRIMARY_DISPOSITIONS.items()
        if dispositions[disposition_key] == "approved_for_release"
    ]
    raw_paths = [
        results / "primary" / arm / "raw_results.jsonl"
        for arm in included_arms
    ]
    raw_records = load_raw_results(raw_paths)
    if len(raw_records) != 1800:
        raise ValueError(
            f"model-judge release requires 1,800 responses, got "
            f"{len(raw_records)}"
        )
    records = [
        record for record in raw_records if record["status"] == "success"
    ]
    if len(records) != 1800:
        raise ValueError(
            "model-judge release requires 1,800 successful responses"
        )
    response_ids = {
        str(record["response_id"]) for record in records
    }
    if len(response_ids) != 1800:
        raise ValueError(
            "model-judge release requires 1,800 unique response IDs"
        )
    labels = load_labels(
        results / "judge" / "model_judge_labels_complete.jsonl"
    )
    label_by_id = {label.response_id: label for label in labels}
    if len(labels) != 1800 or len(label_by_id) != 1800:
        raise ValueError("model-judge release requires 1,800 unique labels")
    if any(label.annotator_type != "model" for label in labels):
        raise ValueError("model-judge release contains non-model labels")
    if response_ids != label_by_id.keys():
        missing = response_ids - label_by_id.keys()
        extra = label_by_id.keys() - response_ids
        raise ValueError(
            "model-judge label IDs do not match released responses: "
            f"{len(missing)} missing, {len(extra)} extra"
        )

    labeled_rows = [
        _public_labeled_record(
            record,
            model_label=label_by_id[str(record["response_id"])],
            human_label=None,
        )
        for record in records
    ]
    files: dict[str, bytes] = {
        "README.md": (
            "# Failure-Transparent Agents results\n\n"
            "This release contains 1,800 frozen model-judge labels and the "
            "associated authorized model responses. It is explicitly not "
            "human-validated. No human annotations are included or claimed.\n\n"
            "Provider request IDs, retry errors, credentials, and private "
            "execution-environment identifiers are omitted.\n"
        ).encode("utf-8"),
        "analysis/labeled_results.jsonl": _jsonl_bytes(labeled_rows),
    }
    _copy_artifacts(
        files,
        source=results / "analysis-model-judge",
        destination="analysis",
        relatives=MODEL_ONLY_ARTIFACTS,
    )
    _scan_public_payload(files)
    payload_records = [
        {
            "path": path,
            "sha256": sha256_bytes(content),
            "size_bytes": len(content),
        }
        for path, content in sorted(files.items())
    ]
    manifest = {
        "schema_version": "1.0",
        "project": "failure-transparent-agents",
        "version": source_audit["version"],
        "scientific_status": "model_judge_only_not_human_validated",
        "human_annotations_included": False,
        "human_validation_status": "not_conducted",
        "raw_request_ids_included": False,
        "retry_error_details_included": False,
        "provider_output_dispositions": dispositions,
        "included_primary_arms": included_arms,
        "public_labeled_responses": len(labeled_rows),
        "approval_version_tag": approval["version_tag"],
        "approval_timestamp": approval["approved_at"],
        "payload_file_count": len(payload_records),
        "payload_files": payload_records,
    }
    files["publication-manifest.json"] = canonical_json(manifest)
    _scan_public_payload(files)

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    archive_path = destination / (
        f"failure-transparent-agents-{source_audit['version']}-results.zip"
    )
    prefix = (
        f"failure-transparent-agents-{source_audit['version']}-results/"
    )
    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for relative, content in sorted(files.items()):
            archive.writestr(
                _zip_info(prefix + relative, source_date_epoch),
                content,
            )
    archive_sha256 = sha256_file(archive_path)
    checksum_path = archive_path.with_suffix(".zip.sha256")
    checksum_path.write_text(
        f"{archive_sha256}  {archive_path.name}\n",
        encoding="utf-8",
    )
    report = {
        "schema_version": "1.0",
        "archive": str(archive_path),
        "archive_sha256": archive_sha256,
        "archive_size_bytes": archive_path.stat().st_size,
        "checksum_file": str(checksum_path),
        "public_labeled_responses": len(labeled_rows),
        "included_primary_arms": included_arms,
        "scientific_status": "model_judge_only_not_human_validated",
    }
    report_path = destination / (
        f"failure-transparent-agents-{source_audit['version']}"
        "-results-report.json"
    )
    report_path.write_bytes(canonical_json(report))
    report["report"] = str(report_path)
    return report


def _validate_approval(approval: dict[str, Any], expected_version: str) -> None:
    required = {
        "status": "approved",
        "release_mode": "model_judge_only",
        "human_validation_status": "not_conducted",
        "model_judge_only_release_authorized": True,
        "github_release_authorized": True,
        "raw_request_ids_disposition": "removed",
        "version_tag": expected_version,
    }
    for field, expected in required.items():
        if approval.get(field) != expected:
            raise ValueError(
                f"publication approval {field} must be {expected!r}"
            )
    if not str(approval.get("approved_by") or "").strip():
        raise ValueError("publication approval requires an approver")
    if not str(approval.get("approved_at") or "").strip():
        raise ValueError("publication approval requires a timestamp")
    dispositions = approval.get("provider_output_dispositions")
    expected_keys = {
        "openai_judge",
        "openai_primary_bedrock",
        "anthropic_bedrock",
        "nvidia_bedrock",
    }
    if not isinstance(dispositions, dict) or set(dispositions) != expected_keys:
        raise ValueError("provider output dispositions are incomplete")
    if any(value != "approved_for_release" for value in dispositions.values()):
        raise ValueError(
            "model-judge-only release requires all outputs approved"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument(
        "--approval",
        type=Path,
        default=Path("data/publication_approval.json"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument(
        "--source-date-epoch",
        type=int,
        default=DEFAULT_SOURCE_DATE_EPOCH,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = build_model_only_results_bundle(
        source_root=args.root,
        results_root=args.results_root,
        approval_path=args.approval,
        output_dir=args.output_dir,
        source_date_epoch=args.source_date_epoch,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
