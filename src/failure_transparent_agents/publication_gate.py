"""Audit the scientific and authorization gates for a final public release."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .annotation import load_blinded_packets
from .execution import file_sha256
from .labels import (
    LABEL_NAMES,
    load_labels,
    validate_label_evidence,
)
from .release import audit_release


PROVIDER_DISPOSITIONS = {
    "approved_for_release",
    "excluded_from_public_artifact",
}
REQUEST_ID_DISPOSITIONS = {
    "removed",
    "reviewed_and_approved",
}


def audit_final_publication(
    *,
    source_root: str | Path,
    results_root: str | Path,
    first_labels_path: str | Path,
    second_labels_path: str | Path,
    approval_path: str | Path,
) -> dict[str, Any]:
    """Return a fail-closed audit over scientific and publication artifacts."""

    root = Path(source_root)
    results = Path(results_root)
    first_path = Path(first_labels_path)
    second_path = Path(second_labels_path)
    approval = Path(approval_path)
    errors: list[str] = []
    blockers: list[str] = []

    source_audit = audit_release(root)
    errors.extend(
        f"source release audit: {message}"
        for message in source_audit["errors"]
    )

    packet_path = results / "human" / "human_sample_blinded.jsonl"
    sample_key_path = results / "human" / "human_sample_key.jsonl"
    sample_manifest_path = (
        results / "human" / "human_sample_manifest.json"
    )
    consensus_path = results / "human" / "human_labels.jsonl"
    consensus_manifest_path = (
        results / "human" / "human_labels.manifest.json"
    )
    adjudication_dir = results / "human" / "adjudication"
    agreement_path = adjudication_dir / "human_human_agreement.json"
    adjudication_manifest_path = (
        adjudication_dir / "adjudication_manifest.json"
    )
    sensitivity_dir = results / "analysis-human-sensitivity"
    sensitivity_summary_path = sensitivity_dir / "sensitivity_summary.json"
    model_human_agreement_path = (
        sensitivity_dir / "model_human_agreement.json"
    )
    model_labels_path = (
        results / "judge" / "model_judge_labels_complete.jsonl"
    )
    analysis_dir = results / "analysis"
    analysis_summary_path = analysis_dir / "analysis_summary.json"
    analysis_agreement_path = analysis_dir / "agreement.json"

    packets: dict[str, Mapping[str, Any]] = {}
    if not packet_path.is_file():
        blockers.append("frozen human annotation packet is missing")
    else:
        try:
            loaded_packets = load_blinded_packets(packet_path)
            packets = {
                str(packet["response_id"]): packet
                for packet in loaded_packets
            }
            if len(packets) != 270:
                errors.append(
                    f"human annotation packet has {len(packets)} responses"
                )
        except ValueError as error:
            errors.append(f"human annotation packet is invalid: {error}")

    sample_manifest = _read_json(
        sample_manifest_path,
        "frozen human sample manifest",
        errors,
        blockers,
    )
    if sample_manifest is not None:
        if sample_manifest.get("sample_size") != 270:
            errors.append("frozen human sample does not contain 270 responses")
        _check_manifest_hash(
            sample_manifest,
            "packet_sha256",
            packet_path,
            "frozen human annotation packet",
            errors,
        )
        _check_manifest_hash(
            sample_manifest,
            "private_key_sha256",
            sample_key_path,
            "frozen human sample key",
            errors,
        )

    model_label_count = _audit_model_labels(
        model_labels_path,
        errors,
        blockers,
    )
    first_id = _audit_human_labels(
        first_path,
        "first independent labels",
        packets,
        errors,
        blockers,
    )
    second_id = _audit_human_labels(
        second_path,
        "second independent labels",
        packets,
        errors,
        blockers,
    )
    if first_id is not None and first_id == second_id:
        errors.append("independent human files use the same annotator ID")
    consensus_id = _audit_human_labels(
        consensus_path,
        "human consensus labels",
        packets,
        errors,
        blockers,
    )

    agreement = _read_json(
        agreement_path,
        "human-human agreement",
        errors,
        blockers,
    )
    if agreement is not None:
        if agreement.get("responses") != 270:
            errors.append("human-human agreement does not cover 270 responses")
        if set(agreement.get("metrics", {})) != set(LABEL_NAMES):
            errors.append("human-human agreement does not report all six labels")

    adjudication_manifest = _read_json(
        adjudication_manifest_path,
        "adjudication manifest",
        errors,
        blockers,
    )
    if adjudication_manifest is not None:
        if adjudication_manifest.get("responses") != 270:
            errors.append("adjudication manifest does not cover 270 responses")
        _check_manifest_hash(
            adjudication_manifest,
            "packet_sha256",
            packet_path,
            "adjudication packet",
            errors,
        )
        _check_manifest_hash(
            adjudication_manifest,
            "first_labels_sha256",
            first_path,
            "first independent labels",
            errors,
        )
        _check_manifest_hash(
            adjudication_manifest,
            "second_labels_sha256",
            second_path,
            "second independent labels",
            errors,
        )
        _check_manifest_hash(
            adjudication_manifest,
            "agreement_report_sha256",
            agreement_path,
            "human-human agreement",
            errors,
        )
        disagreement_path = _manifest_sibling_path(
            adjudication_dir,
            adjudication_manifest.get("disagreement_packet"),
            "adjudication disagreement packet",
            errors,
        )
        if disagreement_path is not None:
            _check_manifest_hash(
                adjudication_manifest,
                "disagreement_packet_sha256",
                disagreement_path,
                "adjudication disagreement packet",
                errors,
            )
        fingerprints = adjudication_manifest.get(
            "annotator_fingerprints"
        )
        if not isinstance(fingerprints, dict):
            errors.append("adjudication manifest lacks annotator fingerprints")
        else:
            if (
                first_id is not None
                and fingerprints.get("annotator_a")
                != _fingerprint(first_id)
            ):
                errors.append(
                    "adjudication manifest first annotator does not match"
                )
            if (
                second_id is not None
                and fingerprints.get("annotator_b")
                != _fingerprint(second_id)
            ):
                errors.append(
                    "adjudication manifest second annotator does not match"
                )
        if (
            agreement is not None
            and adjudication_manifest.get("disagreement_responses")
            != agreement.get("disagreement_responses")
        ):
            errors.append(
                "adjudication disagreement count does not match agreement"
            )

    consensus_manifest = _read_json(
        consensus_manifest_path,
        "human consensus manifest",
        errors,
        blockers,
    )
    if consensus_manifest is not None and consensus_path.is_file():
        if consensus_manifest.get("responses") != 270:
            errors.append("human consensus manifest does not cover 270 responses")
        _check_manifest_hash(
            consensus_manifest,
            "output_sha256",
            consensus_path,
            "human consensus labels",
            errors,
        )
        _check_manifest_hash(
            consensus_manifest,
            "packet_sha256",
            packet_path,
            "human consensus packet",
            errors,
        )
        _check_manifest_hash(
            consensus_manifest,
            "first_labels_sha256",
            first_path,
            "human consensus first labels",
            errors,
        )
        _check_manifest_hash(
            consensus_manifest,
            "second_labels_sha256",
            second_path,
            "human consensus second labels",
            errors,
        )
        if (
            consensus_id is not None
            and consensus_manifest.get("consensus_annotator_id") != consensus_id
        ):
            errors.append(
                "human consensus annotator ID does not match its manifest"
            )
        source_fingerprints = consensus_manifest.get(
            "source_annotator_fingerprints"
        )
        if not isinstance(source_fingerprints, dict):
            errors.append("human consensus manifest lacks source fingerprints")
        else:
            expected_first = (
                _fingerprint(first_id) if first_id is not None else None
            )
            expected_second = (
                _fingerprint(second_id) if second_id is not None else None
            )
            if source_fingerprints.get("annotator_a") != expected_first:
                errors.append(
                    "human consensus first annotator does not match"
                )
            if source_fingerprints.get("annotator_b") != expected_second:
                errors.append(
                    "human consensus second annotator does not match"
                )
            adjudicated = consensus_manifest.get(
                "adjudicated_responses"
            )
            adjudicator = source_fingerprints.get("adjudicator")
            if isinstance(adjudicated, int) and adjudicated > 0:
                if not isinstance(adjudicator, str) or not adjudicator:
                    errors.append(
                        "human consensus lacks an adjudicator fingerprint"
                    )
                elif adjudicator in {expected_first, expected_second}:
                    errors.append(
                        "adjudicator is not independent of both annotators"
                    )
            elif adjudicator is not None:
                errors.append(
                    "human consensus names an adjudicator with no disagreements"
                )
        exact = consensus_manifest.get("exact_agreement_responses")
        adjudicated = consensus_manifest.get("adjudicated_responses")
        if (
            not isinstance(exact, int)
            or not isinstance(adjudicated, int)
            or exact + adjudicated != 270
        ):
            errors.append(
                "human consensus agreement and adjudication counts are invalid"
            )
        if (
            adjudication_manifest is not None
            and consensus_manifest.get("adjudicated_responses")
            != adjudication_manifest.get("disagreement_responses")
        ):
            errors.append(
                "human consensus adjudication count does not match preparation"
            )

    analysis_summary = _read_json(
        analysis_summary_path,
        "final full-corpus analysis summary",
        errors,
        blockers,
    )
    if analysis_summary is not None:
        if analysis_summary.get("labeled_responses") != 1800:
            errors.append("final analysis does not cover 1,800 responses")
        if analysis_summary.get("successful_responses") != 1800:
            errors.append("final analysis does not have 1,800 successes")
        if analysis_summary.get("provider_errors") != 0:
            errors.append("final analysis contains provider errors")
        if analysis_summary.get("agreement_available") is not True:
            errors.append("final analysis lacks model-human agreement")
    analysis_agreement = _read_json(
        analysis_agreement_path,
        "final analysis agreement",
        errors,
        blockers,
    )
    if analysis_agreement is not None:
        _audit_agreement(
            analysis_agreement,
            "final analysis agreement",
            errors,
        )
    _require_files(
        analysis_dir,
        (
            "labeled_results.jsonl",
            "rates.csv",
            "comparisons.csv",
            "efficiency.csv",
            "figures/figure1_false_success_by_model.svg",
            "figures/figure2_transparency_and_utility.svg",
            "figures/figure3_pressure_ablation.svg",
            "tables/ablation_table.tex",
        ),
        "final analysis",
        blockers,
    )

    sensitivity = _read_json(
        sensitivity_summary_path,
        "human sensitivity summary",
        errors,
        blockers,
    )
    if sensitivity is not None:
        if sensitivity.get("sampled_responses") != 270:
            errors.append("human sensitivity does not cover 270 responses")
        if (
            sensitivity.get("scientific_status")
            != "human_validation_sensitivity"
        ):
            errors.append("human sensitivity has the wrong scientific status")
        if sensitivity.get("analysis_status") != "post_freeze_descriptive":
            errors.append("human sensitivity is not marked post-freeze")
        if sensitivity.get("frozen_sample_authenticated") is not True:
            errors.append("human sensitivity did not authenticate its sample")
        if (
            sample_manifest_path.is_file()
            and sensitivity.get("frozen_sample_manifest_sha256")
            != file_sha256(sample_manifest_path)
        ):
            errors.append(
                "human sensitivity sample-manifest hash does not match"
            )
        if (
            sample_key_path.is_file()
            and sensitivity.get("frozen_sample_key_sha256")
            != file_sha256(sample_key_path)
        ):
            errors.append("human sensitivity sample-key hash does not match")
        if not sensitivity.get("model_human_agreement_available"):
            errors.append("human sensitivity lacks model-human agreement")
        if (
            consensus_id is not None
            and sensitivity.get("human_annotator_id") != consensus_id
        ):
            errors.append(
                "human sensitivity uses a different consensus annotator"
            )
    _require_files(
        sensitivity_dir,
        (
            "human_labeled_sample.jsonl",
            "human_rates.csv",
            "human_primary_comparisons.csv",
        ),
        "human sensitivity",
        blockers,
    )

    model_human_agreement = _read_json(
        model_human_agreement_path,
        "model-human agreement",
        errors,
        blockers,
    )
    if model_human_agreement is not None:
        _audit_agreement(
            model_human_agreement,
            "model-human agreement",
            errors,
        )

    approval_record = _read_json(
        approval,
        "publication approval",
        errors,
        blockers,
    )
    if approval_record is not None:
        _audit_approval(
            approval_record,
            expected_version=f"v{source_audit['version']}",
            errors=errors,
            blockers=blockers,
        )

    return {
        "schema_version": "1.0",
        "source_root": str(root),
        "results_root": str(results),
        "source_release_local_ready": source_audit["local_release_ready"],
        "source_release_reported_publication_ready": source_audit[
            "publication_ready"
        ],
        "source_version": source_audit["version"],
        "human_packet_responses": len(packets),
        "model_judge_labels": model_label_count,
        "final_analysis_labeled_responses": (
            analysis_summary.get("labeled_responses")
            if analysis_summary is not None
            else None
        ),
        "first_annotator_id": first_id,
        "second_annotator_id": second_id,
        "consensus_annotator_id": consensus_id,
        "errors": sorted(set(errors)),
        "publication_blockers": sorted(set(blockers)),
        "final_publication_ready": not errors and not blockers,
    }


def _audit_human_labels(
    path: Path,
    description: str,
    packets: Mapping[str, Mapping[str, Any]],
    errors: list[str],
    blockers: list[str],
) -> str | None:
    if not path.is_file():
        blockers.append(f"{description} are missing: {path}")
        return None
    try:
        labels = load_labels(path)
    except ValueError as error:
        errors.append(f"{description} are invalid: {error}")
        return None
    annotator_ids = {label.annotator_id for label in labels}
    if len(annotator_ids) != 1:
        errors.append(f"{description} must use exactly one annotator ID")
        return None
    if any(label.annotator_type != "human" for label in labels):
        errors.append(f"{description} contain non-human labels")
    by_id = {label.response_id: label for label in labels}
    if len(labels) != 270 or len(by_id) != 270:
        errors.append(f"{description} must contain 270 unique responses")
    if packets and set(by_id) != set(packets):
        errors.append(f"{description} do not match the frozen packet")
    if packets:
        for response_id, label in by_id.items():
            packet = packets.get(response_id)
            if packet is None:
                continue
            try:
                validate_label_evidence(
                    label,
                    str(packet["assistant_response"]),
                )
            except ValueError as error:
                errors.append(
                    f"{description} contain invalid evidence for "
                    f"{response_id}: {error}"
                )
                break
    return next(iter(annotator_ids))


def _audit_model_labels(
    path: Path,
    errors: list[str],
    blockers: list[str],
) -> int:
    if not path.is_file():
        blockers.append(f"complete frozen model-judge labels are missing: {path}")
        return 0
    try:
        labels = load_labels(path)
    except ValueError as error:
        errors.append(f"complete frozen model-judge labels are invalid: {error}")
        return 0
    if any(label.annotator_type != "model" for label in labels):
        errors.append("complete frozen model-judge labels contain human labels")
    response_ids = {label.response_id for label in labels}
    if len(labels) != 1800 or len(response_ids) != 1800:
        errors.append(
            "complete frozen model-judge labels must contain "
            "1,800 unique responses"
        )
    return len(response_ids)


def _audit_agreement(
    value: Mapping[str, Any],
    description: str,
    errors: list[str],
) -> None:
    if value.get("shared_responses") != 270:
        errors.append(f"{description} does not cover 270 responses")
    metrics = value.get("metrics")
    if not isinstance(metrics, dict) or set(metrics) != set(LABEL_NAMES):
        errors.append(f"{description} does not report all six labels")


def _require_files(
    root: Path,
    relatives: Sequence[str],
    description: str,
    blockers: list[str],
) -> None:
    for relative in relatives:
        path = root / relative
        if not path.is_file():
            blockers.append(f"{description} artifact is missing: {path}")


def _check_manifest_hash(
    manifest: Mapping[str, Any],
    field: str,
    path: Path,
    description: str,
    errors: list[str],
) -> None:
    if not path.is_file():
        return
    expected = manifest.get(field)
    if not isinstance(expected, str) or expected != file_sha256(path):
        errors.append(f"{description} hash does not match its manifest")


def _manifest_sibling_path(
    root: Path,
    value: Any,
    description: str,
    errors: list[str],
) -> Path | None:
    if not isinstance(value, str) or not value:
        errors.append(f"{description} filename is missing")
        return None
    relative = Path(value)
    if relative.name != value:
        errors.append(f"{description} filename is unsafe")
        return None
    path = root / relative
    if not path.is_file():
        errors.append(f"{description} is missing: {path}")
        return None
    return path


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _read_json(
    path: Path,
    description: str,
    errors: list[str],
    blockers: list[str],
) -> dict[str, Any] | None:
    if not path.is_file():
        blockers.append(f"{description} is missing: {path}")
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{description} is invalid JSON: {error}")
        return None
    if not isinstance(value, dict):
        errors.append(f"{description} must be a JSON object")
        return None
    return value


def _audit_approval(
    approval: Mapping[str, Any],
    *,
    expected_version: str,
    errors: list[str],
    blockers: list[str],
) -> None:
    if approval.get("schema_version") != "1.0":
        errors.append("publication approval schema_version must be 1.0")
    if approval.get("status") != "approved":
        blockers.append("publication approval status is not approved")
    if not str(approval.get("approved_by") or "").strip():
        blockers.append("publication approval has no approver")
    approved_at = approval.get("approved_at")
    if not isinstance(approved_at, str):
        blockers.append("publication approval has no timestamp")
    else:
        try:
            parsed = datetime.fromisoformat(approved_at)
            if parsed.tzinfo is None:
                errors.append(
                    "publication approval timestamp must include a timezone"
                )
        except ValueError:
            errors.append("publication approval timestamp is invalid")
    if approval.get("version_tag") != expected_version:
        blockers.append(
            f"publication approval must name version {expected_version}"
        )
    if approval.get("human_validation_reviewed") is not True:
        blockers.append("human validation has not been author-reviewed")
    if approval.get("github_release_authorized") is not True:
        blockers.append("GitHub release has not been authorized")
    if (
        approval.get("raw_request_ids_disposition")
        not in REQUEST_ID_DISPOSITIONS
    ):
        blockers.append("raw request IDs have no approved disposition")
    provider_outputs = approval.get("provider_output_dispositions")
    if not isinstance(provider_outputs, dict):
        blockers.append("provider output dispositions are missing")
    else:
        expected = {
            "openai_judge",
            "openai_primary_bedrock",
            "anthropic_bedrock",
            "nvidia_bedrock",
        }
        if set(provider_outputs) != expected:
            errors.append("provider output dispositions have unexpected keys")
        for provider in expected:
            if provider_outputs.get(provider) not in PROVIDER_DISPOSITIONS:
                blockers.append(
                    f"provider output disposition is pending for {provider}"
                )


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
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = audit_final_publication(
        source_root=args.root,
        results_root=args.results_root,
        first_labels_path=args.first_labels,
        second_labels_path=args.second_labels,
        approval_path=args.approval,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["final_publication_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
