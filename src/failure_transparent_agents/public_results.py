"""Build a deterministic, disclosure-aware public scientific-results bundle."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping, Sequence
import zipfile

from .analysis import load_raw_results
from .final_release import PRIVATE_PATTERNS
from .labels import ResponseLabel, load_labels
from .publication_gate import audit_final_publication
from .release import (
    DEFAULT_SOURCE_DATE_EPOCH,
    SECRET_PATTERNS,
    canonical_json,
    sha256_bytes,
    sha256_file,
)


PRIMARY_DISPOSITIONS = {
    "openai": "openai_primary_bedrock",
    "anthropic": "anthropic_bedrock",
    "nvidia": "nvidia_bedrock",
}
ANALYSIS_ARTIFACTS = (
    "analysis_summary.json",
    "rates.csv",
    "comparisons.csv",
    "efficiency.csv",
    "agreement.json",
    "figures/figure1_false_success_by_model.svg",
    "figures/figure2_transparency_and_utility.svg",
    "figures/figure3_pressure_ablation.svg",
    "tables/ablation_table.tex",
)
SENSITIVITY_ARTIFACTS = (
    "sensitivity_summary.json",
    "human_rates.csv",
    "human_primary_comparisons.csv",
    "model_human_agreement.json",
)
def build_public_results_bundle(
    *,
    source_root: str | Path,
    results_root: str | Path,
    first_labels_path: str | Path,
    second_labels_path: str | Path,
    approval_path: str | Path,
    output_dir: str | Path,
    source_date_epoch: int = DEFAULT_SOURCE_DATE_EPOCH,
) -> dict[str, Any]:
    """Build a public bundle only after the final publication gate passes."""

    gate = audit_final_publication(
        source_root=source_root,
        results_root=results_root,
        first_labels_path=first_labels_path,
        second_labels_path=second_labels_path,
        approval_path=approval_path,
    )
    if not gate["final_publication_ready"]:
        messages = [*gate["errors"], *gate["publication_blockers"]]
        raise ValueError(
            "final publication gate failed: " + "; ".join(messages)
        )
    if source_date_epoch < DEFAULT_SOURCE_DATE_EPOCH:
        raise ValueError(
            f"source_date_epoch must be at least {DEFAULT_SOURCE_DATE_EPOCH}"
        )

    results = Path(results_root)
    approval = _load_json_object(approval_path)
    dispositions = approval["provider_output_dispositions"]
    included_arms = [
        arm
        for arm, disposition_key in PRIMARY_DISPOSITIONS.items()
        if dispositions[disposition_key] == "approved_for_release"
    ]
    excluded_arms = sorted(set(PRIMARY_DISPOSITIONS) - set(included_arms))
    judge_labels_releasable = (
        dispositions["openai_judge"] == "approved_for_release"
    )

    raw_paths = [
        results / "primary" / arm / "raw_results.jsonl"
        for arm in included_arms
    ]
    raw_records = load_raw_results(raw_paths) if raw_paths else []
    model_labels = _labels_by_response(
        load_labels(results / "judge" / "model_judge_labels_complete.jsonl")
    )
    human_labels = _labels_by_response(
        load_labels(results / "human" / "human_labels.jsonl")
    )

    labeled_rows = [
        _public_labeled_record(
            record,
            model_label=(
                model_labels[str(record["response_id"])]
                if judge_labels_releasable
                else None
            ),
            human_label=human_labels.get(str(record["response_id"])),
        )
        for record in raw_records
        if record["status"] == "success"
    ]
    released_ids = {
        str(record["response_id"]) for record in labeled_rows
    }
    released_human_labels = [
        label.to_dict()
        for response_id, label in sorted(human_labels.items())
        if response_id in released_ids
    ]
    human_subset = [
        record
        for record in labeled_rows
        if record["human_consensus_label"] is not None
    ]

    files: dict[str, bytes] = {
        "README.md": _bundle_readme(
            included_arms=included_arms,
            excluded_arms=excluded_arms,
            judge_labels_releasable=judge_labels_releasable,
        ).encode("utf-8"),
        "analysis/labeled_results.jsonl": _jsonl_bytes(labeled_rows),
        "human_validation/human_consensus_labels.jsonl": _jsonl_bytes(
            released_human_labels
        ),
        "human_sensitivity/human_labeled_sample.jsonl": _jsonl_bytes(
            human_subset
        ),
    }
    _copy_artifacts(
        files,
        source=results / "analysis",
        destination="analysis",
        relatives=ANALYSIS_ARTIFACTS,
    )
    _copy_artifacts(
        files,
        source=results / "analysis-human-sensitivity",
        destination="human_sensitivity",
        relatives=SENSITIVITY_ARTIFACTS,
    )
    files["human_validation/human_human_agreement.json"] = (
        results
        / "human"
        / "adjudication"
        / "human_human_agreement.json"
    ).read_bytes()
    files["human_validation/validation_manifest.json"] = canonical_json(
        _public_human_manifest(results)
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
        "version": gate["source_version"],
        "scientific_status": "human_validated_final_results",
        "source_repository": (
            "https://github.com/junru-zhu/failure-transparent-agents"
        ),
        "raw_request_ids_included": False,
        "retry_error_details_included": False,
        "provider_output_dispositions": dispositions,
        "included_primary_arms": included_arms,
        "excluded_primary_arms": excluded_arms,
        "model_judge_labels_included": judge_labels_releasable,
        "public_labeled_responses": len(labeled_rows),
        "public_human_consensus_labels": len(released_human_labels),
        "human_sensitivity_rows": len(human_subset),
        "approval_version_tag": approval["version_tag"],
        "approval_timestamp": approval["approved_at"],
        "payload_file_count": len(payload_records),
        "payload_files": payload_records,
    }
    files["publication-manifest.json"] = canonical_json(manifest)
    _scan_public_payload(files)

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    archive_name = (
        f"failure-transparent-agents-{gate['source_version']}-results.zip"
    )
    archive_path = destination / archive_name
    prefix = (
        f"failure-transparent-agents-{gate['source_version']}-results/"
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
        "public_human_consensus_labels": len(released_human_labels),
        "included_primary_arms": included_arms,
        "excluded_primary_arms": excluded_arms,
        "model_judge_labels_included": judge_labels_releasable,
    }
    report_path = destination / (
        f"failure-transparent-agents-{gate['source_version']}"
        "-results-report.json"
    )
    report_path.write_bytes(canonical_json(report))
    report["report"] = str(report_path)
    return report


def _public_labeled_record(
    record: Mapping[str, Any],
    *,
    model_label: ResponseLabel | None,
    human_label: ResponseLabel | None,
) -> dict[str, Any]:
    usage = record["usage"]
    return {
        "schema_version": "1.0",
        "response_id": record["response_id"],
        "run_id": record["run_id"],
        "scenario_id": record["scenario_id"],
        "base_task_id": record.get("base_task_id"),
        "category": record["category"],
        "task_domain": record["task_domain"],
        "pressure_type": record["pressure_type"],
        "difficulty": record["difficulty"],
        "condition": record["condition"],
        "repeat_index": record["repeat_index"],
        "prompt_version": record["prompt_version"],
        "provider": record["provider"],
        "model": record["model"],
        "response": record["response"],
        "usage": {
            "input_tokens": usage["input_tokens"],
            "cached_input_tokens": usage.get("cached_input_tokens", 0),
            "reasoning_tokens": usage.get("reasoning_tokens", 0),
            "output_tokens": usage["output_tokens"],
            "estimated_cost_usd": usage.get("estimated_cost_usd"),
            "latency_ms": usage["latency_ms"],
            "resolved_model": usage.get("resolved_model"),
            "attempts": usage.get("attempts"),
        },
        "model_judge_label": (
            model_label.to_dict() if model_label is not None else None
        ),
        "human_consensus_label": (
            human_label.to_dict() if human_label is not None else None
        ),
    }


def _public_human_manifest(results: Path) -> dict[str, Any]:
    human = results / "human"
    adjudication = human / "adjudication"
    consensus = _load_json_object(human / "human_labels.manifest.json")
    preparation = _load_json_object(
        adjudication / "adjudication_manifest.json"
    )
    agreement = _load_json_object(
        adjudication / "human_human_agreement.json"
    )
    return {
        "schema_version": "1.0",
        "responses": consensus["responses"],
        "exact_agreement_responses": consensus[
            "exact_agreement_responses"
        ],
        "adjudicated_responses": consensus["adjudicated_responses"],
        "disagreement_responses": preparation["disagreement_responses"],
        "consensus_labels_sha256": consensus["output_sha256"],
        "human_human_agreement_sha256": preparation[
            "agreement_report_sha256"
        ],
        "metrics": sorted(agreement["metrics"]),
        "annotator_identifiers_withheld": True,
        "independent_label_files_withheld": True,
        "adjudication_packet_withheld": True,
    }


def _copy_artifacts(
    files: dict[str, bytes],
    *,
    source: Path,
    destination: str,
    relatives: Sequence[str],
) -> None:
    for relative in relatives:
        files[f"{destination}/{relative}"] = (source / relative).read_bytes()


def _labels_by_response(
    labels: Sequence[ResponseLabel],
) -> dict[str, ResponseLabel]:
    output: dict[str, ResponseLabel] = {}
    for label in labels:
        if label.response_id in output:
            raise ValueError(
                f"multiple labels for response {label.response_id!r}"
            )
        output[label.response_id] = label
    return output


def _load_json_object(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _jsonl_bytes(values: Sequence[Mapping[str, Any]]) -> bytes:
    return "".join(
        json.dumps(value, sort_keys=True) + "\n" for value in values
    ).encode("utf-8")


def _bundle_readme(
    *,
    included_arms: Sequence[str],
    excluded_arms: Sequence[str],
    judge_labels_releasable: bool,
) -> str:
    included = ", ".join(included_arms) if included_arms else "none"
    excluded = ", ".join(excluded_arms) if excluded_arms else "none"
    return (
        "# Failure-Transparent Agents results\n\n"
        "This deterministic bundle contains the human-validated scientific "
        "results authorized for public release.\n\n"
        f"- Included primary arms: {included}\n"
        f"- Excluded primary arms: {excluded}\n"
        "- Provider request IDs and retry error details are omitted.\n"
        "- Independent annotator files and annotator identifiers are "
        "withheld; consensus labels and aggregate agreement are included.\n"
        "- Parsed model-judge labels are "
        f"{'included' if judge_labels_releasable else 'excluded'}.\n"
        "- `publication-manifest.json` records every payload hash and "
        "disclosure decision.\n"
    )


def _scan_public_payload(files: Mapping[str, bytes]) -> None:
    for path, content in files.items():
        for label, pattern in {
            **SECRET_PATTERNS,
            **PRIVATE_PATTERNS,
        }.items():
            if pattern.search(content):
                raise ValueError(f"possible {label} in public result {path}")


def _zip_info(name: str, source_date_epoch: int) -> zipfile.ZipInfo:
    timestamp = datetime.fromtimestamp(
        source_date_epoch,
        tz=timezone.utc,
    )
    info = zipfile.ZipInfo(
        filename=name,
        date_time=(
            timestamp.year,
            timestamp.month,
            timestamp.day,
            timestamp.hour,
            timestamp.minute,
            timestamp.second,
        ),
    )
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    info.create_system = 3
    return info


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--first-labels", type=Path, required=True)
    parser.add_argument("--second-labels", type=Path, required=True)
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
    report = build_public_results_bundle(
        source_root=args.root,
        results_root=args.results_root,
        first_labels_path=args.first_labels,
        second_labels_path=args.second_labels,
        approval_path=args.approval,
        output_dir=args.output_dir,
        source_date_epoch=args.source_date_epoch,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
