"""Prepare blinded human disagreements and finalize one consensus label set."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from .annotation import load_blinded_packets
from .execution import file_sha256
from .labels import (
    LABEL_NAMES,
    ResponseLabel,
    load_labels,
    validate_label_evidence,
)
from .statistics import agreement


def prepare_adjudication(
    *,
    packet_path: str | Path,
    first_labels_path: str | Path,
    second_labels_path: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Compare two complete human label sets and write blinded disagreements."""

    packets = load_blinded_packets(packet_path)
    packet_by_id = {str(packet["response_id"]): packet for packet in packets}
    expected_ids = set(packet_by_id)
    first_by_id, first_annotator = _load_complete_human_labels(
        first_labels_path,
        packet_by_id=packet_by_id,
        expected_ids=expected_ids,
        label="first labels",
    )
    second_by_id, second_annotator = _load_complete_human_labels(
        second_labels_path,
        packet_by_id=packet_by_id,
        expected_ids=expected_ids,
        label="second labels",
    )
    if first_annotator == second_annotator:
        raise ValueError("independent label files must use different annotator IDs")

    ordered_ids = [str(packet["response_id"]) for packet in packets]
    disagreement_ids = [
        response_id
        for response_id in ordered_ids
        if _disagreement_labels(
            first_by_id[response_id],
            second_by_id[response_id],
        )
    ]
    metrics = {
        name: agreement(
            [getattr(first_by_id[response_id], name) for response_id in ordered_ids],
            [getattr(second_by_id[response_id], name) for response_id in ordered_ids],
        )
        for name in LABEL_NAMES
    }
    disagreements = [
        _build_disagreement_packet(
            packet_by_id[response_id],
            first_by_id[response_id],
            second_by_id[response_id],
        )
        for response_id in disagreement_ids
    ]
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    disagreement_path = destination / "adjudication_blinded.jsonl"
    _write_jsonl(disagreement_path, disagreements)
    agreement_path = destination / "human_human_agreement.json"
    agreement_report = {
        "schema_version": "1.0",
        "responses": len(ordered_ids),
        "exact_binary_agreement_responses": len(ordered_ids)
        - len(disagreement_ids),
        "disagreement_responses": len(disagreement_ids),
        "metrics": metrics,
    }
    _write_json(agreement_path, agreement_report)
    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "packet_path": str(packet_path),
        "packet_sha256": file_sha256(packet_path),
        "first_labels_path": str(first_labels_path),
        "first_labels_sha256": file_sha256(first_labels_path),
        "second_labels_path": str(second_labels_path),
        "second_labels_sha256": file_sha256(second_labels_path),
        "annotator_fingerprints": {
            "annotator_a": _fingerprint(first_annotator),
            "annotator_b": _fingerprint(second_annotator),
        },
        "responses": len(ordered_ids),
        "disagreement_responses": len(disagreement_ids),
        "disagreement_packet": disagreement_path.name,
        "disagreement_packet_sha256": file_sha256(disagreement_path),
        "agreement_report": agreement_path.name,
        "agreement_report_sha256": file_sha256(agreement_path),
    }
    _write_json(destination / "adjudication_manifest.json", manifest)
    return manifest


def finalize_adjudication(
    *,
    packet_path: str | Path,
    first_labels_path: str | Path,
    second_labels_path: str | Path,
    adjudicated_labels_path: str | Path | None,
    output_path: str | Path,
    consensus_annotator_id: str = "human-consensus-v1",
) -> dict[str, Any]:
    """Merge exact agreements with third-reviewer decisions."""

    consensus_id = consensus_annotator_id.strip()
    if not consensus_id:
        raise ValueError("consensus_annotator_id must be non-empty")
    packets = load_blinded_packets(packet_path)
    packet_by_id = {str(packet["response_id"]): packet for packet in packets}
    expected_ids = set(packet_by_id)
    first_by_id, first_annotator = _load_complete_human_labels(
        first_labels_path,
        packet_by_id=packet_by_id,
        expected_ids=expected_ids,
        label="first labels",
    )
    second_by_id, second_annotator = _load_complete_human_labels(
        second_labels_path,
        packet_by_id=packet_by_id,
        expected_ids=expected_ids,
        label="second labels",
    )
    if first_annotator == second_annotator:
        raise ValueError("independent label files must use different annotator IDs")
    ordered_ids = [str(packet["response_id"]) for packet in packets]
    disagreement_ids = {
        response_id
        for response_id in ordered_ids
        if _disagreement_labels(
            first_by_id[response_id],
            second_by_id[response_id],
        )
    }
    adjudicated_by_id: dict[str, ResponseLabel] = {}
    adjudicator_fingerprint = None
    if disagreement_ids:
        if adjudicated_labels_path is None:
            raise ValueError("adjudicated labels are required for disagreements")
        adjudicated_by_id, adjudicator_id = _load_complete_human_labels(
            adjudicated_labels_path,
            packet_by_id=packet_by_id,
            expected_ids=disagreement_ids,
            label="adjudicated labels",
        )
        adjudicator_fingerprint = _fingerprint(adjudicator_id)
    elif adjudicated_labels_path is not None:
        labels = load_labels(adjudicated_labels_path)
        if labels:
            raise ValueError("adjudicated labels supplied but no disagreements exist")

    final_labels: list[ResponseLabel] = []
    for response_id in ordered_ids:
        if response_id in disagreement_ids:
            source = adjudicated_by_id[response_id]
            notes = "Adjudicated after independent-label disagreement."
            if source.notes:
                notes += f" {source.notes}"
            final = ResponseLabel(
                response_id=response_id,
                annotator_id=consensus_id,
                annotator_type="human",
                evidence_spans=source.evidence_spans,
                confidence=source.confidence,
                notes=notes,
                **{name: bool(getattr(source, name)) for name in LABEL_NAMES},
            )
        else:
            final = _agreed_consensus_label(
                first_by_id[response_id],
                second_by_id[response_id],
                consensus_annotator_id=consensus_id,
            )
        validate_label_evidence(
            final,
            str(packet_by_id[response_id]["assistant_response"]),
        )
        final_labels.append(final)

    destination = Path(output_path)
    _write_jsonl(destination, [label.to_dict() for label in final_labels])
    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "packet_path": str(packet_path),
        "packet_sha256": file_sha256(packet_path),
        "first_labels_sha256": file_sha256(first_labels_path),
        "second_labels_sha256": file_sha256(second_labels_path),
        "adjudicated_labels_sha256": (
            file_sha256(adjudicated_labels_path)
            if adjudicated_labels_path is not None
            else None
        ),
        "source_annotator_fingerprints": {
            "annotator_a": _fingerprint(first_annotator),
            "annotator_b": _fingerprint(second_annotator),
            "adjudicator": adjudicator_fingerprint,
        },
        "consensus_annotator_id": consensus_id,
        "responses": len(final_labels),
        "exact_agreement_responses": len(final_labels) - len(disagreement_ids),
        "adjudicated_responses": len(disagreement_ids),
        "output_path": str(destination),
        "output_sha256": file_sha256(destination),
    }
    manifest_path = destination.with_suffix(".manifest.json")
    _write_json(manifest_path, manifest)
    return manifest


def _load_complete_human_labels(
    path: str | Path,
    *,
    packet_by_id: Mapping[str, Mapping[str, Any]],
    expected_ids: set[str],
    label: str,
) -> tuple[dict[str, ResponseLabel], str]:
    labels = load_labels(path)
    annotator_ids = {item.annotator_id for item in labels}
    if len(annotator_ids) != 1:
        raise ValueError(f"{label} must contain exactly one annotator")
    if any(item.annotator_type != "human" for item in labels):
        raise ValueError(f"{label} must contain only human annotations")
    by_id = {item.response_id: item for item in labels}
    if set(by_id) != expected_ids:
        missing = sorted(expected_ids - by_id.keys())
        extra = sorted(by_id.keys() - expected_ids)
        raise ValueError(
            f"{label} response set mismatch: missing={missing}, extra={extra}"
        )
    for response_id, item in by_id.items():
        packet = packet_by_id[response_id]
        validate_label_evidence(item, str(packet["assistant_response"]))
    return by_id, next(iter(annotator_ids))


def _disagreement_labels(
    first: ResponseLabel,
    second: ResponseLabel,
) -> list[str]:
    return [
        name
        for name in LABEL_NAMES
        if bool(getattr(first, name)) != bool(getattr(second, name))
    ]


def _build_disagreement_packet(
    packet: Mapping[str, Any],
    first: ResponseLabel,
    second: ResponseLabel,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "response_id": packet["response_id"],
        "scenario": packet["scenario"],
        "assistant_response": packet["assistant_response"],
        "disagreement_labels": _disagreement_labels(first, second),
        "annotations": {
            "annotator_a": _blinded_label(first),
            "annotator_b": _blinded_label(second),
        },
        "adjudication_template": packet["annotation_template"],
    }


def _blinded_label(label: ResponseLabel) -> dict[str, Any]:
    return {
        **{name: bool(getattr(label, name)) for name in LABEL_NAMES},
        "evidence_spans": {
            name: list(label.evidence_spans[name]) for name in LABEL_NAMES
        },
        "confidence": label.confidence,
        "notes": label.notes,
    }


def _agreed_consensus_label(
    first: ResponseLabel,
    second: ResponseLabel,
    *,
    consensus_annotator_id: str,
) -> ResponseLabel:
    disagreements = _disagreement_labels(first, second)
    if disagreements:
        raise ValueError("cannot construct agreement label from a disagreement")
    evidence: dict[str, tuple[str, ...]] = {}
    for name in LABEL_NAMES:
        combined: list[str] = []
        for span in (*first.evidence_spans[name], *second.evidence_spans[name]):
            if span not in combined:
                combined.append(span)
        evidence[name] = tuple(combined)
    notes = "Independent annotators agreed on all binary labels."
    if first.notes:
        notes += f" Annotator A note: {first.notes}"
    if second.notes:
        notes += f" Annotator B note: {second.notes}"
    return ResponseLabel(
        response_id=first.response_id,
        annotator_id=consensus_annotator_id,
        annotator_type="human",
        evidence_spans=evidence,
        confidence=min(first.confidence, second.confidence),
        notes=notes,
        **{name: bool(getattr(first, name)) for name in LABEL_NAMES},
    )


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _write_jsonl(path: Path, values: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True) + "\n")
    temporary.replace(path)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--packets", type=Path, required=True)
    prepare.add_argument("--first", type=Path, required=True)
    prepare.add_argument("--second", type=Path, required=True)
    prepare.add_argument("--output-dir", type=Path, required=True)
    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--packets", type=Path, required=True)
    finalize.add_argument("--first", type=Path, required=True)
    finalize.add_argument("--second", type=Path, required=True)
    finalize.add_argument("--adjudicated", type=Path)
    finalize.add_argument("--output", type=Path, required=True)
    finalize.add_argument(
        "--consensus-annotator-id",
        default="human-consensus-v1",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "prepare":
        result = prepare_adjudication(
            packet_path=args.packets,
            first_labels_path=args.first,
            second_labels_path=args.second,
            output_dir=args.output_dir,
        )
    else:
        result = finalize_adjudication(
            packet_path=args.packets,
            first_labels_path=args.first,
            second_labels_path=args.second,
            adjudicated_labels_path=args.adjudicated,
            output_path=args.output,
            consensus_annotator_id=args.consensus_annotator_id,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
