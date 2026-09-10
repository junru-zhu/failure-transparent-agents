"""Direct provider adapters with usage accounting and conservative budgets."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from typing import Any, Mapping, Protocol
import urllib.error
import urllib.request
from urllib.parse import urlparse

from .prompting import build_system_instruction, build_user_message
from .providers import (
    GenerationRequest,
    GenerationResponse,
    ModelProvider,
    ProviderError,
)


@dataclass(frozen=True)
class Pricing:
    """USD prices per million tokens supplied in a frozen run configuration."""

    input_per_million: float
    cached_input_per_million: float
    output_per_million: float

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "Pricing":
        required = {
            "input_per_million",
            "cached_input_per_million",
            "output_per_million",
        }
        _require_exact_fields(value, required, "pricing")
        parsed = {
            key: _nonnegative_number(value[key], f"pricing.{key}") for key in required
        }
        return cls(**parsed)

    def estimate(
        self,
        *,
        input_tokens: int,
        cached_input_tokens: int,
        output_tokens: int,
    ) -> float:
        uncached = max(0, input_tokens - cached_input_tokens)
        return (
            uncached * self.input_per_million
            + cached_input_tokens * self.cached_input_per_million
            + output_tokens * self.output_per_million
        ) / 1_000_000


class DollarBudget:
    """Thread-safe reservation budget that refuses unsafe concurrent launches."""

    def __init__(self, max_usd: float) -> None:
        if max_usd <= 0:
            raise ValueError("max_usd must be positive")
        self.max_usd = float(max_usd)
        self.spent_usd = 0.0
        self.reserved_usd = 0.0
        self._lock = threading.Lock()

    def reserve(self, amount_usd: float) -> float:
        if amount_usd < 0:
            raise ValueError("reservation must be nonnegative")
        with self._lock:
            projected = self.spent_usd + self.reserved_usd + amount_usd
            if projected > self.max_usd + 1e-12:
                raise ProviderError(
                    "budget cap would be exceeded: "
                    f"${projected:.6f} > ${self.max_usd:.6f}"
                )
            self.reserved_usd += amount_usd
        return amount_usd

    def settle(self, reservation_usd: float, actual_usd: float) -> None:
        if actual_usd < 0:
            raise ValueError("actual cost must be nonnegative")
        with self._lock:
            self.reserved_usd -= reservation_usd
            self.spent_usd += actual_usd
            if actual_usd > reservation_usd + 1e-12:
                raise ProviderError(
                    "provider-reported cost exceeded the conservative "
                    f"reservation: ${actual_usd:.6f} > ${reservation_usd:.6f}"
                )
            if self.spent_usd > self.max_usd + 1e-12:
                raise ProviderError(
                    f"actual cost exceeded budget cap ${self.max_usd:.6f}"
                )

    def charge_reservation(self, reservation_usd: float) -> None:
        """Conservatively charge the upper bound when billing is uncertain."""

        self.settle(reservation_usd, reservation_usd)

    def restore_spent(self, amount_usd: float) -> None:
        """Restore persisted spend before resuming an interrupted run."""

        if amount_usd < 0:
            raise ValueError("restored spend must be nonnegative")
        with self._lock:
            if amount_usd > self.max_usd + 1e-12:
                raise ProviderError(
                    f"persisted spend exceeds budget cap ${self.max_usd:.6f}"
                )
            if self.spent_usd or self.reserved_usd:
                raise ProviderError("budget spend can only be restored before calls")
            self.spent_usd = amount_usd


@dataclass(frozen=True)
class ProviderSettings:
    provider_type: str
    provider_name: str
    model: str
    base_url: str
    api_key_env: str
    max_output_tokens: int
    temperature: float | None
    timeout_seconds: float
    max_retries: int
    max_calls: int
    max_budget_usd: float
    pricing: Pricing
    extra_headers: dict[str, str]
    extra_body: dict[str, Any]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ProviderSettings":
        required = {
            "provider_type",
            "provider_name",
            "model",
            "base_url",
            "api_key_env",
            "max_output_tokens",
            "temperature",
            "timeout_seconds",
            "max_retries",
            "max_calls",
            "max_budget_usd",
            "pricing",
            "extra_headers",
            "extra_body",
        }
        _require_exact_fields(value, required, "provider settings")
        provider_type = _nonempty_string(value["provider_type"], "provider_type")
        if provider_type not in {
            "openai_responses",
            "anthropic_messages",
            "openai_chat_compatible",
            "aws_bedrock_invoke_model",
            "aws_bedrock_anthropic_messages",
        }:
            raise ValueError(f"unsupported provider_type {provider_type!r}")
        temperature_value = value["temperature"]
        if temperature_value is not None:
            temperature_value = _number(temperature_value, "temperature")
            if not 0 <= temperature_value <= 2:
                raise ValueError("temperature must be between 0 and 2")
        extra_headers_value = value["extra_headers"]
        if not isinstance(extra_headers_value, dict):
            raise ValueError("extra_headers must be an object")
        extra_headers = {
            _nonempty_string(key, "extra_headers key"): _nonempty_string(
                item,
                f"extra_headers.{key}",
            )
            for key, item in extra_headers_value.items()
        }
        extra_body_value = value["extra_body"]
        if not isinstance(extra_body_value, dict):
            raise ValueError("extra_body must be an object")
        _validate_json_value(extra_body_value, "extra_body")
        max_output_tokens = _positive_int(
            value["max_output_tokens"],
            "max_output_tokens",
        )
        max_retries = _nonnegative_int(value["max_retries"], "max_retries")
        return cls(
            provider_type=provider_type,
            provider_name=_nonempty_string(value["provider_name"], "provider_name"),
            model=_nonempty_string(value["model"], "model"),
            base_url=_nonempty_string(value["base_url"], "base_url").rstrip("/"),
            api_key_env=_nonempty_string(value["api_key_env"], "api_key_env"),
            max_output_tokens=max_output_tokens,
            temperature=temperature_value,
            timeout_seconds=_positive_number(
                value["timeout_seconds"],
                "timeout_seconds",
            ),
            max_retries=max_retries,
            max_calls=_positive_int(value["max_calls"], "max_calls"),
            max_budget_usd=_positive_number(
                value["max_budget_usd"],
                "max_budget_usd",
            ),
            pricing=Pricing.from_dict(_mapping(value["pricing"], "pricing")),
            extra_headers=extra_headers,
            extra_body=dict(extra_body_value),
        )


class JsonTransport(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> tuple[dict[str, Any], Mapping[str, str]]:
        """POST JSON and return decoded response plus response headers."""


class UrllibJsonTransport:
    """Small dependency-free JSON transport for reproducible API calls."""

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> tuple[dict[str, Any], Mapping[str, str]]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers=dict(headers),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                body = response.read().decode("utf-8")
                decoded = json.loads(body)
                if not isinstance(decoded, dict):
                    raise ProviderError("provider returned a non-object JSON response")
                return decoded, dict(response.headers.items())
        except urllib.error.HTTPError as error:
            body = error.read().decode("utf-8", errors="replace")
            raise ProviderError(
                f"provider HTTP {error.code}: {_truncate(body)}"
            ) from error
        except urllib.error.URLError as error:
            raise ProviderError(f"provider network error: {error.reason}") from error
        except (TimeoutError, OSError) as error:
            raise ProviderError(f"provider transport error: {error}") from error
        except json.JSONDecodeError as error:
            raise ProviderError("provider returned invalid JSON") from error


class AwsCliJsonTransport:
    """Invoke one Bedrock model with temporary SigV4 credentials via AWS CLI."""

    def __init__(
        self,
        *,
        profile: str,
        region: str,
        model: str,
        aws_command: str = "aws",
        runner: Any = None,
    ) -> None:
        self.profile = _nonempty_string(profile, "AWS profile")
        self.region = _nonempty_string(region, "AWS region")
        self.model = _nonempty_string(model, "Bedrock model")
        self.aws_command = _nonempty_string(aws_command, "AWS command")
        self._runner = runner or subprocess.run

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        payload: Mapping[str, Any],
        timeout_seconds: float,
    ) -> tuple[dict[str, Any], Mapping[str, str]]:
        del url, headers
        with tempfile.TemporaryDirectory(prefix="fta-bedrock-") as directory:
            root = Path(directory)
            request_path = root / "request.json"
            response_path = root / "response.json"
            request_path.write_text(
                json.dumps(payload, separators=(",", ":")),
                encoding="utf-8",
            )
            command = [
                self.aws_command,
                "bedrock-runtime",
                "invoke-model",
                "--profile",
                self.profile,
                "--region",
                self.region,
                "--model-id",
                self.model,
                "--content-type",
                "application/json",
                "--accept",
                "application/json",
                "--cli-binary-format",
                "raw-in-base64-out",
                "--body",
                f"fileb://{request_path}",
                str(response_path),
            ]
            try:
                completed = self._runner(
                    command,
                    check=False,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
            except FileNotFoundError as error:
                raise ProviderError(
                    f"AWS CLI executable was not found: {self.aws_command!r}"
                ) from error
            except subprocess.TimeoutExpired as error:
                raise ProviderError(
                    f"Bedrock invocation exceeded {timeout_seconds:g} seconds"
                ) from error
            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip()
                raise ProviderError(
                    f"AWS Bedrock CLI exited with status "
                    f"{completed.returncode}: {_truncate(detail)}"
                )
            try:
                decoded = json.loads(response_path.read_text(encoding="utf-8"))
            except FileNotFoundError as error:
                raise ProviderError(
                    "AWS Bedrock CLI produced no response file"
                ) from error
            except json.JSONDecodeError as error:
                raise ProviderError(
                    "AWS Bedrock CLI returned invalid JSON"
                ) from error
            if not isinstance(decoded, dict):
                raise ProviderError(
                    "AWS Bedrock CLI returned a non-object JSON response"
                )
            return decoded, {}


class DirectApiProvider(ModelProvider):
    """Shared call cap, retry, latency, and budget behavior."""

    def __init__(
        self,
        settings: ProviderSettings,
        *,
        api_key: str | None = None,
        transport: JsonTransport | None = None,
    ) -> None:
        self.settings = settings
        self.name = settings.provider_name
        self.model = settings.model
        self._api_key = api_key or os.environ.get(settings.api_key_env)
        if not self._api_key:
            raise ValueError(
                f"missing API key environment variable {settings.api_key_env}"
            )
        self._transport = transport or UrllibJsonTransport()
        self._budget = DollarBudget(settings.max_budget_usd)
        self._calls_started = 0
        self._call_lock = threading.Lock()

    @property
    def spent_usd(self) -> float:
        return self._budget.spent_usd

    @property
    def calls_started(self) -> int:
        with self._call_lock:
            return self._calls_started

    def maximum_cost(self, request: GenerationRequest) -> float:
        """Return the conservative per-attempt upper bound for one request."""

        return self.maximum_text_cost(
            build_system_instruction(request),
            build_user_message(request),
        )

    def maximum_text_cost(
        self,
        system_instruction: str,
        user_message: str,
    ) -> float:
        """Return the conservative per-attempt bound for arbitrary text input."""

        return self._maximum_call_cost(system_instruction, user_message)

    def preflight_required_budget(
        self,
        requests: list[GenerationRequest],
    ) -> float:
        """Return the worst-case matrix cost including every configured retry."""

        attempts = self.settings.max_retries + 1
        return sum(self.maximum_cost(request) for request in requests) * attempts

    def restore_spent_usd(self, amount_usd: float) -> None:
        self._budget.restore_spent(amount_usd)

    def restore_runtime_state(
        self,
        *,
        spent_usd: float,
        calls_started: int,
    ) -> None:
        """Restore persisted budget and call-cap state before a resumed run."""

        if (
            not isinstance(calls_started, int)
            or isinstance(calls_started, bool)
            or calls_started < 0
        ):
            raise ValueError("calls_started must be a nonnegative integer")
        if calls_started > self.settings.max_calls:
            raise ProviderError(
                f"persisted calls exceed call cap {self.settings.max_calls}"
            )
        self._budget.restore_spent(spent_usd)
        with self._call_lock:
            if self._calls_started:
                raise ProviderError("call state can only be restored before calls")
            self._calls_started = calls_started

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        return self.generate_text(
            build_system_instruction(request),
            build_user_message(request),
        )

    def generate_text(
        self,
        system_instruction: str,
        user_message: str,
    ) -> GenerationResponse:
        """Generate from provider-neutral system and user strings."""

        max_cost = self._maximum_call_cost(system_instruction, user_message)
        attempt_errors: list[str] = []
        for attempt_index in range(self.settings.max_retries + 1):
            self._claim_call()
            reservation = self._budget.reserve(max_cost)
            reservation_open = True
            started = time.perf_counter()
            try:
                payload = self._payload(system_instruction, user_message)
                data, headers = self._transport.post(
                    self._endpoint(),
                    headers=self._headers(),
                    payload=payload,
                    timeout_seconds=self.settings.timeout_seconds,
                )
                parsed = self._parse_response(data)
                latency_ms = round((time.perf_counter() - started) * 1000)
                actual_cost = self.settings.pricing.estimate(
                    input_tokens=parsed["input_tokens"],
                    cached_input_tokens=parsed["cached_input_tokens"],
                    output_tokens=parsed["output_tokens"],
                )
                try:
                    self._budget.settle(reservation, actual_cost)
                finally:
                    reservation_open = False
                return GenerationResponse(
                    provider=self.name,
                    model=self.model,
                    text=parsed["text"],
                    input_tokens=parsed["input_tokens"],
                    cached_input_tokens=parsed["cached_input_tokens"],
                    reasoning_tokens=parsed["reasoning_tokens"],
                    output_tokens=parsed["output_tokens"],
                    estimated_cost_usd=actual_cost,
                    latency_ms=latency_ms,
                    provider_request_id=parsed["request_id"]
                    or _header(headers, "x-request-id"),
                    resolved_model=parsed["resolved_model"],
                    attempts=attempt_index + 1,
                    attempt_errors=tuple(attempt_errors),
                )
            except ProviderError as error:
                if reservation_open:
                    self._budget.charge_reservation(reservation)
                attempt_errors.append(str(error))
                if attempt_index >= self.settings.max_retries:
                    raise ProviderError(
                        f"{self.name} failed after {attempt_index + 1} attempt(s): "
                        f"{attempt_errors[-1]}"
                    ) from error
        raise AssertionError("unreachable retry loop")

    def _claim_call(self) -> None:
        with self._call_lock:
            if self._calls_started >= self.settings.max_calls:
                raise ProviderError(
                    f"provider call cap reached: "
                    f"{self._calls_started}/{self.settings.max_calls}"
                )
            self._calls_started += 1

    def _maximum_call_cost(self, system_instruction: str, user_message: str) -> float:
        input_token_upper_bound = len(system_instruction) + len(user_message) + 1024
        return self.settings.pricing.estimate(
            input_tokens=input_token_upper_bound,
            cached_input_tokens=0,
            output_tokens=self.settings.max_output_tokens,
        )

    def _endpoint(self) -> str:
        raise NotImplementedError

    def _headers(self) -> dict[str, str]:
        raise NotImplementedError

    def _payload(
        self,
        system_instruction: str,
        user_message: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def _parse_response(self, data: Mapping[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def _merge_extra_body(self, payload: dict[str, Any]) -> dict[str, Any]:
        overlap = payload.keys() & self.settings.extra_body.keys()
        if overlap:
            raise ProviderError(
                "extra_body cannot override managed fields: "
                + ", ".join(sorted(overlap))
            )
        return {**payload, **self.settings.extra_body}


class OpenAIResponsesProvider(DirectApiProvider):
    def _endpoint(self) -> str:
        return f"{self.settings.base_url}/responses"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            **self.settings.extra_headers,
        }

    def _payload(
        self,
        system_instruction: str,
        user_message: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "instructions": system_instruction,
            "input": user_message,
            "max_output_tokens": self.settings.max_output_tokens,
            "store": False,
        }
        if self.settings.temperature is not None:
            payload["temperature"] = self.settings.temperature
        return self._merge_extra_body(payload)

    def _parse_response(self, data: Mapping[str, Any]) -> dict[str, Any]:
        text = data.get("output_text")
        if not isinstance(text, str) or not text.strip():
            text_parts: list[str] = []
            for item in _list(data.get("output"), "output"):
                if not isinstance(item, dict) or item.get("type") != "message":
                    continue
                for content in _list(item.get("content"), "output content"):
                    if (
                        isinstance(content, dict)
                        and content.get("type") == "output_text"
                        and isinstance(content.get("text"), str)
                    ):
                        text_parts.append(content["text"])
            text = "\n".join(text_parts)
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("OpenAI response contained no output text")
        usage = _mapping(data.get("usage"), "usage")
        input_details = _mapping(
            usage.get("input_tokens_details", {}),
            "input_tokens_details",
        )
        output_details = _mapping(
            usage.get("output_tokens_details", {}),
            "output_tokens_details",
        )
        return {
            "text": text.strip(),
            "input_tokens": _usage_int(usage, "input_tokens"),
            "cached_input_tokens": _optional_usage_int(
                input_details,
                "cached_tokens",
            ),
            "reasoning_tokens": _optional_usage_int(
                output_details,
                "reasoning_tokens",
            ),
            "output_tokens": _usage_int(usage, "output_tokens"),
            "request_id": _optional_string(data.get("id")),
            "resolved_model": _optional_string(data.get("model")),
        }


class AnthropicMessagesProvider(DirectApiProvider):
    def _endpoint(self) -> str:
        return f"{self.settings.base_url}/v1/messages"

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
            **self.settings.extra_headers,
        }

    def _payload(
        self,
        system_instruction: str,
        user_message: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "system": system_instruction,
            "messages": [{"role": "user", "content": user_message}],
            "max_tokens": self.settings.max_output_tokens,
        }
        if self.settings.temperature is not None:
            payload["temperature"] = self.settings.temperature
        return self._merge_extra_body(payload)

    def _parse_response(self, data: Mapping[str, Any]) -> dict[str, Any]:
        text_parts = [
            block["text"]
            for block in _list(data.get("content"), "content")
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ]
        if not text_parts:
            raise ProviderError("Anthropic response contained no text block")
        usage = _mapping(data.get("usage"), "usage")
        return {
            "text": "\n".join(text_parts).strip(),
            "input_tokens": _usage_int(usage, "input_tokens"),
            "cached_input_tokens": _optional_usage_int(
                usage,
                "cache_read_input_tokens",
            ),
            "reasoning_tokens": 0,
            "output_tokens": _usage_int(usage, "output_tokens"),
            "request_id": _optional_string(data.get("id")),
            "resolved_model": _optional_string(data.get("model")),
        }


class OpenAICompatibleChatProvider(DirectApiProvider):
    def _endpoint(self) -> str:
        return f"{self.settings.base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            **self.settings.extra_headers,
        }

    def _payload(
        self,
        system_instruction: str,
        user_message: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": self.settings.max_output_tokens,
            "stream": False,
        }
        if self.settings.temperature is not None:
            payload["temperature"] = self.settings.temperature
        return self._merge_extra_body(payload)

    def _parse_response(self, data: Mapping[str, Any]) -> dict[str, Any]:
        choices = _list(data.get("choices"), "choices")
        if not choices or not isinstance(choices[0], dict):
            raise ProviderError("chat response contained no choice")
        message = _mapping(choices[0].get("message"), "choice message")
        text = message.get("content")
        if not isinstance(text, str) or not text.strip():
            raise ProviderError("chat response contained no message content")
        usage = _mapping(data.get("usage"), "usage")
        prompt_details = _mapping(
            usage.get("prompt_tokens_details", {}),
            "prompt_tokens_details",
        )
        return {
            "text": text.strip(),
            "input_tokens": _usage_int(usage, "prompt_tokens"),
            "cached_input_tokens": _optional_usage_int(
                prompt_details,
                "cached_tokens",
            ),
            "reasoning_tokens": 0,
            "output_tokens": _usage_int(usage, "completion_tokens"),
            "request_id": _optional_string(data.get("id")),
            "resolved_model": _optional_string(data.get("model")),
        }


class AwsBedrockInvokeModelProvider(OpenAICompatibleChatProvider):
    """Native Bedrock InvokeModel adapter using AWS profile/SigV4 auth."""

    def _endpoint(self) -> str:
        return self.settings.base_url

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def _payload(
        self,
        system_instruction: str,
        user_message: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": self.settings.max_output_tokens,
        }
        if self.settings.temperature is not None:
            payload["temperature"] = self.settings.temperature
        return self._merge_extra_body(payload)


class AwsBedrockAnthropicMessagesProvider(AnthropicMessagesProvider):
    """Anthropic Messages schema over native Bedrock InvokeModel."""

    def _endpoint(self) -> str:
        return self.settings.base_url

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def _payload(
        self,
        system_instruction: str,
        user_message: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "system": system_instruction,
            "messages": [{"role": "user", "content": user_message}],
            "max_tokens": self.settings.max_output_tokens,
        }
        if self.settings.temperature is not None:
            payload["temperature"] = self.settings.temperature
        return self._merge_extra_body(payload)


def build_api_provider(
    settings: ProviderSettings,
    *,
    api_key: str | None = None,
    transport: JsonTransport | None = None,
) -> DirectApiProvider:
    aws_provider_types = {
        "aws_bedrock_invoke_model": AwsBedrockInvokeModelProvider,
        "aws_bedrock_anthropic_messages": AwsBedrockAnthropicMessagesProvider,
    }
    if settings.provider_type in aws_provider_types:
        profile = api_key or os.environ.get(settings.api_key_env)
        if not profile:
            raise ValueError(
                f"missing AWS profile environment variable "
                f"{settings.api_key_env}"
            )
        resolved_transport = transport or AwsCliJsonTransport(
            profile=profile,
            region=_aws_bedrock_region(settings.base_url),
            model=_aws_bedrock_model_id(settings),
        )
        return aws_provider_types[settings.provider_type](
            settings,
            api_key=profile,
            transport=resolved_transport,
        )
    providers = {
        "openai_responses": OpenAIResponsesProvider,
        "anthropic_messages": AnthropicMessagesProvider,
        "openai_chat_compatible": OpenAICompatibleChatProvider,
    }
    return providers[settings.provider_type](
        settings,
        api_key=api_key,
        transport=transport,
    )


def _aws_bedrock_region(base_url: str) -> str:
    hostname = urlparse(base_url).hostname or ""
    for prefix, suffix in (
        ("bedrock-mantle.", ".api.aws"),
        ("bedrock-runtime.", ".amazonaws.com"),
    ):
        if hostname.startswith(prefix) and hostname.endswith(suffix):
            region = hostname[len(prefix) : -len(suffix)]
            if region:
                return region
    raise ValueError("Bedrock base_url does not encode an AWS region")


def _aws_bedrock_model_id(settings: ProviderSettings) -> str:
    path = urlparse(settings.base_url).path
    prefix = "/model/"
    if path.startswith(prefix):
        model_id = path[len(prefix) :].strip("/")
        if model_id:
            return model_id
    return settings.model


def load_provider_settings(path: str) -> ProviderSettings:
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("provider settings file must contain an object")
    return ProviderSettings.from_dict(value)


def _mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ProviderError(f"{field} must be an object")
    return value


def _list(value: Any, field: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProviderError(f"{field} must be an array")
    return value


def _usage_int(value: Mapping[str, Any], key: str) -> int:
    item = value.get(key)
    if not isinstance(item, int) or isinstance(item, bool) or item < 0:
        raise ProviderError(f"usage.{key} must be a nonnegative integer")
    return item


def _optional_usage_int(value: Mapping[str, Any], key: str) -> int:
    item = value.get(key, 0)
    if not isinstance(item, int) or isinstance(item, bool) or item < 0:
        raise ProviderError(f"usage.{key} must be a nonnegative integer")
    return item


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _validate_json_value(value: Any, field: str) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{field}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError(f"{field} keys must be non-empty strings")
            _validate_json_value(item, f"{field}.{key}")
        return
    raise ValueError(f"{field} must contain only JSON values")


def _header(headers: Mapping[str, str], key: str) -> str | None:
    for name, value in headers.items():
        if name.casefold() == key.casefold():
            return value
    return None


def _require_exact_fields(
    value: Mapping[str, Any],
    required: set[str],
    label: str,
) -> None:
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


def _number(value: Any, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{field} must be a number")
    return float(value)


def _positive_number(value: Any, field: str) -> float:
    parsed = _number(value, field)
    if parsed <= 0:
        raise ValueError(f"{field} must be positive")
    return parsed


def _nonnegative_number(value: Any, field: str) -> float:
    parsed = _number(value, field)
    if parsed < 0:
        raise ValueError(f"{field} must be nonnegative")
    return parsed


def _positive_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def _truncate(value: str, limit: int = 500) -> str:
    normalized = " ".join(value.split())
    return normalized if len(normalized) <= limit else normalized[:limit] + "..."
