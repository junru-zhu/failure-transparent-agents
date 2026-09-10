"""Failure-transparency benchmark for tool-using language-model agents."""

from .conditions import Condition
from .evaluate import Evaluation, evaluate_response
from .labels import LABEL_NAMES, ResponseLabel, load_labels
from .schema import (
    Difficulty,
    FailureCategory,
    PressureType,
    Scenario,
    ToolObservation,
    load_scenarios,
)
from .simulator import FailedToolSimulator

__all__ = [
    "Condition",
    "Difficulty",
    "Evaluation",
    "FailureCategory",
    "FailedToolSimulator",
    "LABEL_NAMES",
    "PressureType",
    "ResponseLabel",
    "Scenario",
    "ToolObservation",
    "evaluate_response",
    "load_labels",
    "load_scenarios",
]

__version__ = "0.2.0"
