"""Validated condition-blinded annotation labels."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


LABEL_NAMES = (
    "false_success",
    "fabricated_details",
    "limitation_disclosed",
    "recovery_action",
    "useful_response",
    "over_refusal",
)


@dataclass(frozen=True)
class ResponseLabel:
    """One annotator's labels for one model response."""

    response_id: str
    annotator_id: str
    annotator_type: str
    false_success: bool
    fabricated_details: bool
    limitation_disclosed: bool
    recovery_action: bool
    useful_response: bool
    over_refusal: bool
    evidence_spans: dict[str, tuple[str, ...]]
    confidence: int
    notes: str
    schema_version: str = "1.0"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "ResponseLabel":
        required = {
            "schema_version",
            "response_id",
            "annotator_id",
            "annotator_type",
            *LABEL_NAMES,
            "evidence_spans",
            "confidence",
            "notes",
        }
        _require_exact_fields(value, required)
        if value["schema_version"] != "1.0":
            raise ValueError("label schema_version must be '1.0'")
        annotator_type = _nonempty_string(
            value["annotator_type"],
            "annotator_type",
        )
        if annotator_type not in {"human", "model"}:
            raise ValueError("annotator_type must be 'human' or 'model'")
        labels: dict[str, bool] = {}
        for name in LABEL_NAMES:
            item = value[name]
            if not isinstance(item, bool):
                raise ValueError(f"{name} must be a boolean")
            labels[name] = item
        evidence_value = value["evidence_spans"]
        if not isinstance(evidence_value, dict):
            raise ValueError("evidence_spans must be an object")
        if set(evidence_value) != set(LABEL_NAMES):
            raise ValueError("evidence_spans must contain every label name")
        evidence_spans: dict[str, tuple[str, ...]] = {}
        for name in LABEL_NAMES:
            spans = evidence_value[name]
            if not isinstance(spans, list):
                raise ValueError(f"evidence_spans.{name} must be an array")
            evidence_spans[name] = tuple(
                _nonempty_string(span, f"evidence_spans.{name}[{index}]")
                for index, span in enumerate(spans)
            )
        confidence = value["confidence"]
        if not isinstance(confidence, int) or isinstance(confidence, bool):
            raise ValueError("confidence must be an integer")
        if confidence not in {1, 2, 3}:
            raise ValueError("confidence must be 1, 2, or 3")
        notes = value["notes"]
        if not isinstance(notes, str):
            raise ValueError("notes must be a string")
        return cls(
            response_id=_nonempty_string(value["response_id"], "response_id"),
            annotator_id=_nonempty_string(value["annotator_id"], "annotator_id"),
            annotator_type=annotator_type,
            evidence_spans=evidence_spans,
            confidence=confidence,
            notes=notes.strip(),
            **labels,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "response_id": self.response_id,
            "annotator_id": self.annotator_id,
            "annotator_type": self.annotator_type,
            **{name: getattr(self, name) for name in LABEL_NAMES},
            "evidence_spans": {
                name: list(self.evidence_spans[name]) for name in LABEL_NAMES
            },
            "confidence": self.confidence,
            "notes": self.notes,
        }


def load_labels(path: str | Path) -> list[ResponseLabel]:
    """Load JSONL labels and reject duplicate annotator-response pairs."""

    source = Path(path)
    labels: list[ResponseLabel] = []
    seen: set[tuple[str, str]] = set()
    with source.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                value = json.loads(raw_line)
            except json.JSONDecodeError as error:
                raise ValueError(
                    f"{source}:{line_number}: invalid JSON: {error.msg}"
                ) from error
            if not isinstance(value, dict):
                raise ValueError(f"{source}:{line_number}: label must be an object")
            try:
                label = ResponseLabel.from_dict(value)
            except ValueError as error:
                raise ValueError(f"{source}:{line_number}: {error}") from error
            key = (label.response_id, label.annotator_id)
            if key in seen:
                raise ValueError(
                    f"{source}:{line_number}: duplicate label for {key!r}"
                )
            seen.add(key)
            labels.append(label)
    if not labels:
        raise ValueError(f"{source}: no labels found")
    return labels


def validate_label_evidence(
    label: ResponseLabel,
    assistant_response: str,
) -> None:
    """Require positive verbatim spans and empty spans for negative labels."""

    if not isinstance(assistant_response, str):
        raise ValueError("assistant_response must be a string")
    for name in LABEL_NAMES:
        spans = label.evidence_spans[name]
        positive = bool(getattr(label, name))
        if positive and not spans:
            raise ValueError(f"positive label {name} requires evidence span")
        if not positive and spans:
            raise ValueError(f"negative label {name} must have empty spans")
        for span in spans:
            if span not in assistant_response:
                raise ValueError(
                    f"evidence span for {name} is not verbatim in the response"
                )


def _require_exact_fields(value: dict[str, Any], required: set[str]) -> None:
    missing = required - value.keys()
    extra = value.keys() - required
    if missing:
        raise ValueError(f"label missing fields: {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"label has unexpected fields: {', '.join(sorted(extra))}")


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()
