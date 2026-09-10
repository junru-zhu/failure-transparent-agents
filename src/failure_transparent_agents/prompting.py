"""Provider-neutral prompt construction for the benchmark."""

from __future__ import annotations

import json

from .conditions import PROMPTS
from .providers import GenerationRequest


def build_system_instruction(request: GenerationRequest) -> str:
    """Return only the preregistered condition instruction."""

    return PROMPTS[request.condition]


def build_user_message(request: GenerationRequest) -> str:
    """Render the user request followed by the deterministic failed-tool trace."""

    observation = request.scenario.tool_observation
    tool_trace = json.dumps(
        {
            "name": observation.name,
            "status": observation.status,
            "error_code": observation.error_code,
            "message": observation.message,
            "metadata": observation.metadata,
        },
        sort_keys=True,
    )
    return "\n\n".join(
        (
            "USER REQUEST:\n" + request.scenario.user_request,
            "TOOL OBSERVATION:\n" + tool_trace,
            "Respond to the user after observing this tool result.",
        )
    )
