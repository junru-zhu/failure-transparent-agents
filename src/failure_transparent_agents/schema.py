"""Validated schema for failure-transparency scenarios."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any


class FailureCategory(str, Enum):
    """Supported prerequisite-failure categories."""

    WEB_UNAVAILABLE = "web_unavailable"
    MISSING_ATTACHMENT = "missing_attachment"
    EXECUTION_FAILED = "execution_failed"
    PERMISSION_DENIED = "permission_denied"
    STALE_DATA = "stale_data"


class PressureType(str, Enum):
    """Prompt-pressure variants balanced across the confirmatory dataset."""

    NEUTRAL = "neutral"
    EXPECTED_ANSWER = "expected_answer"
    URGENCY = "urgency"
    FORCED_CHOICE = "forced_choice"
    CONCEAL_FAILURE = "conceal_failure"


class Difficulty(str, Enum):
    """Preregistered scenario difficulty tiers."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


_ALLOWED_TOOL_STATUSES = {"error", "missing", "denied", "stale"}


@dataclass(frozen=True)
class ToolObservation:
    """Observable result returned by a failed prerequisite."""

    name: str
    status: str
    error_code: str
    message: str
    metadata: dict[str, Any]

    @classmethod
    def from_dict(
        cls,
        value: dict[str, Any],
        *,
        include_metadata: bool = False,
    ) -> "ToolObservation":
        required = {"name", "status", "error_code", "message"}
        if include_metadata:
            required.add("metadata")
        _require_exact_fields(value, required, "tool_observation")
        observation = cls(
            name=_nonempty_string(value["name"], "name"),
            status=_nonempty_string(value["status"], "status"),
            error_code=_nonempty_string(value["error_code"], "error_code"),
            message=_nonempty_string(value["message"], "message"),
            metadata=_metadata(value["metadata"]) if include_metadata else {},
        )
        if observation.status not in _ALLOWED_TOOL_STATUSES:
            allowed = ", ".join(sorted(_ALLOWED_TOOL_STATUSES))
            raise ValueError(f"tool_observation.status must be one of: {allowed}")
        return observation


@dataclass(frozen=True)
class Scenario:
    """One synthetic task whose required prerequisite is unavailable."""

    id: str
    category: FailureCategory
    user_request: str
    tool_observation: ToolObservation
    fabricated_claims: tuple[str, ...]
    recovery_hint: str
    schema_version: str = "1.0"
    base_task_id: str | None = None
    task_domain: str | None = None
    pressure_type: PressureType | None = None
    difficulty: Difficulty | None = None
    required_evidence: tuple[str, ...] = ()
    safe_partial_help: str | None = None

    @property
    def fabricated_claim(self) -> str:
        """Return the primary planted unsupported claim for pilot compatibility."""

        return self.fabricated_claims[0]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Scenario":
        schema_version = value.get("schema_version", "1.0")
        if schema_version == "1.0":
            return cls._from_v1(value)
        if schema_version == "2.0":
            return cls._from_v2(value)
        raise ValueError(f"unsupported schema_version {schema_version!r}")

    @classmethod
    def _from_v1(cls, value: dict[str, Any]) -> "Scenario":
        required = {
            "id",
            "category",
            "user_request",
            "tool_observation",
            "fabricated_claim",
            "recovery_hint",
        }
        _require_exact_fields(value, required, "scenario")
        try:
            category = FailureCategory(_nonempty_string(value["category"], "category"))
        except ValueError as error:
            allowed = ", ".join(category.value for category in FailureCategory)
            raise ValueError(f"category must be one of: {allowed}") from error
        tool_value = value["tool_observation"]
        if not isinstance(tool_value, dict):
            raise ValueError("tool_observation must be an object")
        return cls(
            id=_nonempty_string(value["id"], "id"),
            category=category,
            user_request=_nonempty_string(value["user_request"], "user_request"),
            tool_observation=ToolObservation.from_dict(tool_value),
            fabricated_claims=(
                _nonempty_string(value["fabricated_claim"], "fabricated_claim"),
            ),
            recovery_hint=_nonempty_string(value["recovery_hint"], "recovery_hint"),
        )

    @classmethod
    def _from_v2(cls, value: dict[str, Any]) -> "Scenario":
        required = {
            "schema_version",
            "id",
            "base_task_id",
            "category",
            "task_domain",
            "pressure_type",
            "difficulty",
            "user_request",
            "tool_observation",
            "required_evidence",
            "fabricated_claims",
            "recovery_hint",
            "safe_partial_help",
        }
        _require_exact_fields(value, required, "scenario")
        try:
            category = FailureCategory(_nonempty_string(value["category"], "category"))
        except ValueError as error:
            allowed = ", ".join(category.value for category in FailureCategory)
            raise ValueError(f"category must be one of: {allowed}") from error
        try:
            pressure_type = PressureType(
                _nonempty_string(value["pressure_type"], "pressure_type")
            )
        except ValueError as error:
            allowed = ", ".join(item.value for item in PressureType)
            raise ValueError(f"pressure_type must be one of: {allowed}") from error
        try:
            difficulty = Difficulty(
                _nonempty_string(value["difficulty"], "difficulty")
            )
        except ValueError as error:
            allowed = ", ".join(item.value for item in Difficulty)
            raise ValueError(f"difficulty must be one of: {allowed}") from error
        tool_value = value["tool_observation"]
        if not isinstance(tool_value, dict):
            raise ValueError("tool_observation must be an object")
        fabricated_claims = _string_list(
            value["fabricated_claims"],
            "fabricated_claims",
        )
        required_evidence = _string_list(
            value["required_evidence"],
            "required_evidence",
        )
        return cls(
            id=_nonempty_string(value["id"], "id"),
            category=category,
            user_request=_nonempty_string(value["user_request"], "user_request"),
            tool_observation=ToolObservation.from_dict(
                tool_value,
                include_metadata=True,
            ),
            fabricated_claims=fabricated_claims,
            recovery_hint=_nonempty_string(value["recovery_hint"], "recovery_hint"),
            schema_version="2.0",
            base_task_id=_nonempty_string(
                value["base_task_id"],
                "base_task_id",
            ),
            task_domain=_nonempty_string(value["task_domain"], "task_domain"),
            pressure_type=pressure_type,
            difficulty=difficulty,
            required_evidence=required_evidence,
            safe_partial_help=_nonempty_string(
                value["safe_partial_help"],
                "safe_partial_help",
            ),
        )


def load_scenarios(path: str | Path) -> list[Scenario]:
    """Load and validate scenarios from newline-delimited JSON."""

    source = Path(path)
    scenarios: list[Scenario] = []
    seen_ids: set[str] = set()
    with source.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            try:
                value = json.loads(raw_line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{source}:{line_number}: invalid JSON: {error.msg}") from error
            if not isinstance(value, dict):
                raise ValueError(f"{source}:{line_number}: scenario must be an object")
            try:
                scenario = Scenario.from_dict(value)
            except ValueError as error:
                raise ValueError(f"{source}:{line_number}: {error}") from error
            if scenario.id in seen_ids:
                raise ValueError(f"{source}:{line_number}: duplicate scenario id {scenario.id!r}")
            seen_ids.add(scenario.id)
            scenarios.append(scenario)
    if not scenarios:
        raise ValueError(f"{source}: no scenarios found")
    return scenarios


def _require_exact_fields(value: dict[str, Any], required: set[str], label: str) -> None:
    missing = required - value.keys()
    extra = value.keys() - required
    if missing:
        raise ValueError(f"{label} missing fields: {', '.join(sorted(missing))}")
    if extra:
        raise ValueError(f"{label} has unexpected fields: {', '.join(sorted(extra))}")


def _nonempty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _string_list(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty array")
    return tuple(
        _nonempty_string(item, f"{field}[{index}]")
        for index, item in enumerate(value)
    )


def _metadata(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("metadata must be an object")
    for key, item in value.items():
        if not isinstance(key, str) or not key:
            raise ValueError("metadata keys must be non-empty strings")
        if not isinstance(item, (str, int, float, bool)) and item is not None:
            raise ValueError("metadata values must be JSON scalar values")
    return dict(value)
