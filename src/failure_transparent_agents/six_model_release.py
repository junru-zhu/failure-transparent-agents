"""Build the sanitized six-model, model-judge-only results release."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence
import zipfile

from .public_results import (
    _copy_artifacts,
    _jsonl_bytes,
    _load_json_object,
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


SIX_MODEL_ARTIFACTS = (
    "analysis_summary.json",
    "rates.csv",
    "comparisons.csv",
    "efficiency.csv",
    "figures/figure1_false_success_by_model.svg",
    "figures/figure2_transparency_and_utility.svg",
    "figures/figure3_pressure_ablation.svg",
    "tables/ablation_table.tex",
)
AUDIT_ARTIFACTS = (
    "model_extension_manifest.json",
    "model_extension_summary.json",
    "model_extension_verification.json",
    "model_extension_span_audit.json",
)
EXPECTED_CONDITIONS = {
    "baseline": 1200,
    "transparency": 1200,
    "evidence_contract": 1200,
}
EXPECTED_MODELS = {
    "us.openai.gpt-5.6-terra": 600,
    "claude-sonnet-5": 600,
    "nvidia.nemotron-super-3-120b": 600,
    "us.amazon.nova-micro-v1:0": 600,
    "us.meta.llama3-1-8b-instruct-v1:0": 600,
    "mistral.ministral-3-8b-instruct": 600,
}
EXPECTED_DISPOSITIONS = {
    "openai_luna_judge",
    "openai_primary_bedrock",
    "anthropic_bedrock",
    "nvidia_bedrock",
    "amazon_nova_bedrock",
    "meta_llama_bedrock",
    "mistral_bedrock",
}
OUTCOMES = (
    "false_success",
    "fabricated_details",
    "limitation_disclosed",
    "recovery_action",
    "useful_response",
    "over_refusal",
)


def build_six_model_results_bundle(
    *,
    source_root: str | Path,
    analysis_root: str | Path,
    approval_path: str | Path,
    output_dir: str | Path,
    source_date_epoch: int = DEFAULT_SOURCE_DATE_EPOCH,
) -> dict[str, Any]:
    """Build a deterministic public archive from the unified analysis rows."""

    root = Path(source_root)
    analysis = Path(analysis_root)
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

    rows = _load_labeled_rows(analysis / "labeled_results.jsonl")
    public_rows = [_public_six_model_record(row) for row in rows]
    files: dict[str, bytes] = {
        "README.md": _bundle_readme().encode("utf-8"),
        "analysis/labeled_results.jsonl": _jsonl_bytes(public_rows),
    }
    _copy_artifacts(
        files,
        source=analysis,
        destination="analysis",
        relatives=SIX_MODEL_ARTIFACTS,
    )
    _copy_artifacts(
        files,
        source=root / "data",
        destination="audit",
        relatives=AUDIT_ARTIFACTS,
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
        "study_scope": {
            "original_confirmatory_responses": 1800,
            "post_confirmatory_extension_responses": 1800,
            "unified_six_model_responses": 3600,
        },
        "scientific_status": (
            "confirmatory_original_plus_post_confirmatory_extension_"
            "model_judge_only_not_human_validated"
        ),
        "human_annotations_included": False,
        "human_validation_status": "not_conducted",
        "raw_request_ids_included": False,
        "retry_error_details_included": False,
        "private_execution_environment_details_included": False,
        "included_models": sorted(EXPECTED_MODELS),
        "provider_output_dispositions": approval[
            "provider_output_dispositions"
        ],
        "public_labeled_responses": len(public_rows),
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
        f"failure-transparent-agents-{source_audit['version']}"
        "-six-model-results.zip"
    )
    prefix = (
        f"failure-transparent-agents-{source_audit['version']}"
        "-six-model-results/"
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
        "public_labeled_responses": len(public_rows),
        "included_models": sorted(EXPECTED_MODELS),
        "scientific_status": manifest["scientific_status"],
    }
    report_path = destination / (
        f"failure-transparent-agents-{source_audit['version']}"
        "-six-model-results-report.json"
    )
    report_path.write_bytes(canonical_json(report))
    report["report"] = str(report_path)
    return report


def _load_labeled_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(
                    f"{path}:{line_number} must contain a JSON object"
                )
            rows.append(value)
    if len(rows) != 3600:
        raise ValueError(
            f"six-model release requires 3,600 rows, got {len(rows)}"
        )
    response_ids = [str(row.get("response_id") or "") for row in rows]
    if any(not response_id for response_id in response_ids):
        raise ValueError("six-model release contains an empty response ID")
    if len(set(response_ids)) != 3600:
        raise ValueError(
            "six-model release requires 3,600 unique response IDs"
        )
    if any(row.get("status") != "success" for row in rows):
        raise ValueError("six-model release contains a non-success response")
    if Counter(str(row.get("condition")) for row in rows) != Counter(
        EXPECTED_CONDITIONS
    ):
        raise ValueError("six-model condition counts are incomplete")
    if Counter(str(row.get("model")) for row in rows) != Counter(
        EXPECTED_MODELS
    ):
        raise ValueError("six-model model counts are incomplete")
    if any(row.get("label_annotator_type") != "model" for row in rows):
        raise ValueError("six-model release contains non-model labels")
    for row in rows:
        for outcome in OUTCOMES:
            if not isinstance(row.get(outcome), bool):
                raise ValueError(
                    f"{row['response_id']} has invalid {outcome} label"
                )
    return rows


def _public_six_model_record(row: Mapping[str, Any]) -> dict[str, Any]:
    usage = row.get("usage")
    if not isinstance(usage, Mapping):
        raise ValueError(f"{row.get('response_id')} has invalid usage")
    evidence_spans = row.get("label_evidence_spans")
    if not isinstance(evidence_spans, Mapping):
        raise ValueError(
            f"{row.get('response_id')} has invalid label evidence"
        )
    label = {
        "schema_version": "1.0",
        "response_id": row["response_id"],
        "annotator_id": row["label_annotator_id"],
        "annotator_type": row["label_annotator_type"],
        "confidence": row["label_confidence"],
        "evidence_spans": evidence_spans,
        "notes": row["label_notes"],
    }
    label.update({outcome: row[outcome] for outcome in OUTCOMES})
    return {
        "schema_version": "1.0",
        "response_id": row["response_id"],
        "run_id": row["run_id"],
        "scenario_id": row["scenario_id"],
        "base_task_id": row.get("base_task_id"),
        "category": row["category"],
        "task_domain": row["task_domain"],
        "pressure_type": row["pressure_type"],
        "difficulty": row["difficulty"],
        "condition": row["condition"],
        "repeat_index": row["repeat_index"],
        "prompt_version": row["prompt_version"],
        "provider": row["provider"],
        "model": row["model"],
        "response": row["response"],
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
        "model_judge_label": label,
        "human_consensus_label": None,
    }


def _validate_approval(approval: dict[str, Any], expected_version: str) -> None:
    required = {
        "status": "approved",
        "release_mode": "six_model_model_judge_only",
        "human_validation_status": "not_conducted",
        "six_model_release_authorized": True,
        "github_release_authorized": True,
        "raw_request_ids_disposition": "removed",
        "version_tag": expected_version,
    }
    for field, expected in required.items():
        if approval.get(field) != expected:
            raise ValueError(
                f"six-model publication approval {field} "
                f"must be {expected!r}"
            )
    if not str(approval.get("approved_by") or "").strip():
        raise ValueError("six-model publication approval requires an approver")
    if not str(approval.get("approved_at") or "").strip():
        raise ValueError(
            "six-model publication approval requires a timestamp"
        )
    dispositions = approval.get("provider_output_dispositions")
    if (
        not isinstance(dispositions, dict)
        or set(dispositions) != EXPECTED_DISPOSITIONS
    ):
        raise ValueError(
            "six-model provider output dispositions are incomplete"
        )
    if any(value != "approved_for_release" for value in dispositions.values()):
        raise ValueError(
            "six-model release requires all outputs approved for release"
        )


def _bundle_readme() -> str:
    return (
        "# Failure-Transparent Agents six-model results\n\n"
        "This deterministic bundle contains 3,600 authorized model responses "
        "and GPT-5.6-Luna labels: the original 1,800-response confirmatory "
        "study and a separate 1,800-response post-confirmatory model "
        "extension. The unified six-model analysis is explicitly not "
        "human-validated.\n\n"
        "- Provider request IDs and retry error details are omitted.\n"
        "- Credentials and private execution-environment details are omitted.\n"
        "- No human annotations or human-agreement claims are included.\n"
        "- `publication-manifest.json` records every payload hash and "
        "disclosure decision.\n"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--analysis-root", type=Path, required=True)
    parser.add_argument(
        "--approval",
        type=Path,
        default=Path("data/six_model_publication_approval.json"),
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
    report = build_six_model_results_bundle(
        source_root=args.root,
        analysis_root=args.analysis_root,
        approval_path=args.approval,
        output_dir=args.output_dir,
        source_date_epoch=args.source_date_epoch,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
