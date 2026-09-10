"""Validate the official-documentation snapshot for model arms and pricing."""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

from .api_providers import ProviderSettings, load_provider_settings
from .execution import file_sha256


SCHEMA_VERSION = "1.0"
TOP_LEVEL_FIELDS = {
    "schema_version",
    "status",
    "verified_at",
    "verification_scope",
    "arms",
}
ARM_FIELDS = {
    "role",
    "config",
    "config_sha256",
    "provider",
    "model",
    "region",
    "provider_type",
    "pricing_usd_per_million_tokens",
    "documented_pricing_usd_per_million_tokens",
    "reservation_pricing_policy",
    "parameter_constraints",
    "sources",
}
PRICE_FIELDS = {"input", "cached_input", "output"}
SOURCE_FIELDS = {"url", "claims"}
ALLOWED_SOURCE_HOSTS = {
    "openai": {"developers.openai.com"},
    "openai-judge": {"developers.openai.com"},
    "anthropic": {"platform.claude.com"},
    "nvidia-bedrock": {"aws.amazon.com", "docs.aws.amazon.com"},
}


def validate_model_verification(
    verification_path: str | Path,
    *,
    provider_config_paths: Sequence[str | Path],
    judge_config_paths: Sequence[str | Path],
) -> dict[str, Any]:
    """Validate one machine-readable provider-documentation snapshot."""

    path = Path(verification_path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise ValueError(f"model verification file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ValueError("model verification must contain valid JSON") from error
    if not isinstance(value, dict):
        raise ValueError("model verification must be an object")
    _require_exact_fields(value, TOP_LEVEL_FIELDS, "model verification")
    if value["schema_version"] != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported model verification schema {value['schema_version']!r}"
        )
    if value["status"] != "verified":
        raise ValueError("model verification status must be 'verified'")
    verified_at = _aware_iso8601(value["verified_at"], "verified_at")
    scope = _nonempty_string(value["verification_scope"], "verification_scope")

    expected: dict[Path, tuple[str, ProviderSettings]] = {}
    for role, config_paths in (
        ("primary", provider_config_paths),
        ("judge", judge_config_paths),
    ):
        for raw_config in config_paths:
            config_path = Path(raw_config)
            resolved = config_path.resolve()
            if resolved in expected:
                raise ValueError(f"duplicate expected config: {config_path}")
            expected[resolved] = (
                role,
                load_provider_settings(str(config_path)),
            )
    if not expected:
        raise ValueError("at least one provider or judge config is required")

    raw_arms = value["arms"]
    if not isinstance(raw_arms, list):
        raise ValueError("model verification arms must be an array")
    seen: set[Path] = set()
    normalized_arms: list[dict[str, Any]] = []
    for index, raw_arm in enumerate(raw_arms):
        if not isinstance(raw_arm, dict):
            raise ValueError(f"arms[{index}] must be an object")
        _require_exact_fields(raw_arm, ARM_FIELDS, f"arms[{index}]")
        config_path = Path(
            _nonempty_string(raw_arm["config"], f"arms[{index}].config")
        )
        resolved = config_path.resolve()
        expected_item = expected.get(resolved)
        if expected_item is None:
            raise ValueError(
                f"arms[{index}] references unexpected config {config_path}"
            )
        if resolved in seen:
            raise ValueError(f"duplicate verified config {config_path}")
        seen.add(resolved)
        expected_role, settings = expected_item
        role = _nonempty_string(raw_arm["role"], f"arms[{index}].role")
        if role != expected_role:
            raise ValueError(f"{config_path}: role must be {expected_role!r}")
        if raw_arm["config_sha256"] != file_sha256(config_path):
            raise ValueError(f"{config_path}: verification config hash is stale")
        _require_equal(
            raw_arm["provider"],
            settings.provider_name,
            f"{config_path}: provider",
        )
        _require_equal(
            raw_arm["model"],
            settings.model,
            f"{config_path}: model",
        )
        _require_equal(
            raw_arm["provider_type"],
            settings.provider_type,
            f"{config_path}: provider_type",
        )
        expected_region = _region(settings)
        if raw_arm["region"] != expected_region:
            raise ValueError(
                f"{config_path}: region must be {expected_region!r}"
            )
        reservation_pricing = _validate_pricing(
            raw_arm["pricing_usd_per_million_tokens"],
            settings,
        )
        documented_pricing = _parse_pricing(
            raw_arm["documented_pricing_usd_per_million_tokens"],
            f"{settings.model}: documented pricing",
        )
        pricing_policy = _validate_pricing_policy(
            raw_arm["reservation_pricing_policy"],
            documented=documented_pricing,
            reservation=reservation_pricing,
            model=settings.model,
        )
        constraints = _validate_constraints(
            raw_arm["parameter_constraints"],
            settings,
            config_path,
        )
        sources = _validate_sources(
            raw_arm["sources"],
            settings.provider_name,
            config_path,
        )
        normalized_arms.append(
            {
                "role": role,
                "config": str(config_path),
                "config_sha256": file_sha256(config_path),
                "provider": settings.provider_name,
                "model": settings.model,
                "region": expected_region,
                "provider_type": settings.provider_type,
                "pricing_usd_per_million_tokens": reservation_pricing,
                "documented_pricing_usd_per_million_tokens": documented_pricing,
                "reservation_pricing_policy": pricing_policy,
                "parameter_constraints": constraints,
                "sources": sources,
            }
        )
    missing = set(expected) - seen
    if missing:
        names = ", ".join(sorted(str(path) for path in missing))
        raise ValueError(f"model verification omits configs: {names}")
    if len(seen) != len(expected):
        raise ValueError("model verification must cover every config exactly once")

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "verified",
        "verified_at": verified_at.isoformat(),
        "verification_scope": scope,
        "path": str(path),
        "sha256": file_sha256(path),
        "arm_count": len(normalized_arms),
        "arms": sorted(normalized_arms, key=lambda arm: arm["config"]),
        "ready": True,
    }


def _validate_pricing(
    value: Any,
    settings: ProviderSettings,
) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ValueError(f"{settings.model}: pricing must be an object")
    _require_exact_fields(value, PRICE_FIELDS, f"{settings.model}: pricing")
    expected = {
        "input": settings.pricing.input_per_million,
        "cached_input": settings.pricing.cached_input_per_million,
        "output": settings.pricing.output_per_million,
    }
    for name, expected_value in expected.items():
        actual = value[name]
        if isinstance(actual, bool) or not isinstance(actual, (int, float)):
            raise ValueError(f"{settings.model}: pricing.{name} must be numeric")
        if abs(float(actual) - expected_value) > 1e-12:
            raise ValueError(
                f"{settings.model}: pricing.{name} does not match config"
            )
    return expected


def _parse_pricing(value: Any, name: str) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    _require_exact_fields(value, PRICE_FIELDS, name)
    parsed: dict[str, float] = {}
    for key in sorted(PRICE_FIELDS):
        item = value[key]
        if (
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or item < 0
        ):
            raise ValueError(f"{name}.{key} must be a nonnegative number")
        parsed[key] = float(item)
    return parsed


def _validate_pricing_policy(
    value: Any,
    *,
    documented: dict[str, float],
    reservation: dict[str, float],
    model: str,
) -> str:
    policy = _nonempty_string(value, f"{model}: reservation_pricing_policy")
    if policy == "documented-current-rate":
        if documented != reservation:
            raise ValueError(
                f"{model}: current-rate reservation must equal documented pricing"
            )
        return policy
    if policy == "conservative-higher-announced-rate":
        if any(reservation[key] < documented[key] for key in PRICE_FIELDS):
            raise ValueError(
                f"{model}: conservative reservation cannot be below documented pricing"
            )
        if reservation == documented:
            raise ValueError(
                f"{model}: conservative higher-rate policy must reserve more"
            )
        return policy
    raise ValueError(f"{model}: unsupported reservation pricing policy {policy!r}")


def _validate_constraints(
    value: Any,
    settings: ProviderSettings,
    config_path: Path,
) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"{config_path}: parameter_constraints must be an object")
    constraints: dict[str, str] = {}
    for raw_key, raw_value in value.items():
        key = _nonempty_string(raw_key, f"{config_path}: constraint key")
        constraint = _nonempty_string(
            raw_value,
            f"{config_path}: parameter_constraints.{key}",
        )
        constraints[key] = constraint
    temperature = constraints.get("temperature")
    if temperature == "unset":
        if settings.temperature is not None:
            raise ValueError(f"{config_path}: temperature must be unset")
    elif temperature is not None:
        try:
            expected_temperature = float(temperature)
        except ValueError as error:
            raise ValueError(
                f"{config_path}: temperature constraint must be 'unset' or numeric"
            ) from error
        if (
            settings.temperature is None
            or abs(settings.temperature - expected_temperature) > 1e-12
        ):
            raise ValueError(
                f"{config_path}: temperature does not match verification"
            )
    reasoning_effort = constraints.get("reasoning_effort")
    if reasoning_effort is not None:
        reasoning = settings.extra_body.get("reasoning")
        actual = reasoning.get("effort") if isinstance(reasoning, dict) else None
        if actual != reasoning_effort:
            raise ValueError(
                f"{config_path}: reasoning_effort does not match verification"
            )
    if constraints.get("thinking") == "adaptive-default":
        if "thinking" in settings.extra_body:
            raise ValueError(
                f"{config_path}: adaptive-default thinking must remain implicit"
            )
    return dict(sorted(constraints.items()))


def _validate_sources(
    value: Any,
    provider: str,
    config_path: Path,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{config_path}: sources must be a non-empty array")
    allowed_hosts = ALLOWED_SOURCE_HOSTS.get(provider)
    if allowed_hosts is None:
        raise ValueError(f"{config_path}: no source host policy for {provider}")
    sources: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for index, raw_source in enumerate(value):
        if not isinstance(raw_source, dict):
            raise ValueError(f"{config_path}: sources[{index}] must be an object")
        _require_exact_fields(
            raw_source,
            SOURCE_FIELDS,
            f"{config_path}: sources[{index}]",
        )
        url = _nonempty_string(
            raw_source["url"],
            f"{config_path}: sources[{index}].url",
        )
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in allowed_hosts:
            raise ValueError(
                f"{config_path}: source URL must use an approved official host"
            )
        if url in seen_urls:
            raise ValueError(f"{config_path}: duplicate source URL {url}")
        seen_urls.add(url)
        claims = raw_source["claims"]
        if (
            not isinstance(claims, list)
            or not claims
            or any(
                not isinstance(claim, str) or not claim.strip()
                for claim in claims
            )
        ):
            raise ValueError(
                f"{config_path}: sources[{index}].claims must be non-empty strings"
            )
        sources.append(
            {
                "url": url,
                "claims": [claim.strip() for claim in claims],
            }
        )
    return sources


def _region(settings: ProviderSettings) -> str | None:
    if settings.provider_name != "nvidia-bedrock":
        return None
    hostname = urlparse(settings.base_url).hostname or ""
    prefix = "bedrock-mantle."
    suffix = ".api.aws"
    if not hostname.startswith(prefix) or not hostname.endswith(suffix):
        raise ValueError("nvidia-bedrock base URL does not encode an AWS region")
    region = hostname[len(prefix) : -len(suffix)]
    if not region:
        raise ValueError("nvidia-bedrock base URL has an empty region")
    return region


def _aware_iso8601(value: Any, name: str) -> datetime:
    text = _nonempty_string(value, name)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed


def _require_exact_fields(
    value: dict[str, Any],
    expected: set[str],
    name: str,
) -> None:
    actual = set(value)
    if actual != expected:
        raise ValueError(
            f"{name} fields mismatch: "
            f"missing={sorted(expected - actual)}, extra={sorted(actual - expected)}"
        )


def _nonempty_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _require_equal(value: Any, expected: str, name: str) -> None:
    if value != expected:
        raise ValueError(f"{name} must be {expected!r}")
