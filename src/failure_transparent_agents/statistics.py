"""Dependency-free statistics for clustered benchmark analysis."""

from __future__ import annotations

from collections import defaultdict
import itertools
import math
import random
from typing import Any, Iterable, Mapping, Sequence


def hierarchical_rate_interval(
    rows: Sequence[Mapping[str, Any]],
    metric: str,
    *,
    repetitions: int,
    seed: int,
    confidence: float = 0.95,
) -> dict[str, float | int]:
    """Estimate a rate and cluster/repetition bootstrap confidence interval.

    Base tasks are sampled first. Within each selected base task, repeat-level
    responses are sampled within exact model-condition-scenario cells.
    """

    _validate_bootstrap(repetitions, confidence)
    if not rows:
        raise ValueError("cannot estimate a rate from no rows")
    values = [_binary(row[metric], metric) for row in rows]
    clusters = _cluster_rows(rows)
    cluster_cells: dict[str, list[list[int]]] = {}
    for cluster_id, cluster_rows in clusters.items():
        cells: dict[tuple[Any, ...], list[int]] = defaultdict(list)
        for row in cluster_rows:
            cells[_repeat_cell(row)].append(_binary(row[metric], metric))
        cluster_cells[cluster_id] = list(cells.values())
    rng = random.Random(seed)
    estimates: list[float] = []
    cluster_ids = sorted(clusters)
    for _ in range(repetitions):
        sampled: list[int] = []
        for cluster_id in rng.choices(cluster_ids, k=len(cluster_ids)):
            for cell_values in cluster_cells[cluster_id]:
                sampled.extend(rng.choices(cell_values, k=len(cell_values)))
        estimates.append(sum(sampled) / len(sampled))
    alpha = (1 - confidence) / 2
    return {
        "n": len(rows),
        "base_task_clusters": len(clusters),
        "rate": sum(values) / len(values),
        "ci_low": _quantile(estimates, alpha),
        "ci_high": _quantile(estimates, 1 - alpha),
    }


def paired_condition_effect(
    rows: Sequence[Mapping[str, Any]],
    metric: str,
    *,
    baseline: str,
    intervention: str,
    repetitions: int,
    seed: int,
    confidence: float = 0.95,
    permutation_repetitions: int = 100_000,
) -> dict[str, float | int | None]:
    """Estimate a paired condition effect with clustered uncertainty."""

    _validate_bootstrap(repetitions, confidence)
    by_pair: dict[tuple[Any, ...], dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for row in rows:
        condition = str(row["condition"])
        if condition not in {baseline, intervention}:
            continue
        key = (
            row.get("provider"),
            row.get("model"),
            row["scenario_id"],
            int(row["repeat_index"]),
        )
        if condition in by_pair[key]:
            raise ValueError(f"duplicate condition within paired unit: {key!r}")
        by_pair[key][condition] = row

    pairs: list[tuple[str, int, int]] = []
    for unit in by_pair.values():
        if baseline not in unit or intervention not in unit:
            continue
        baseline_row = unit[baseline]
        intervention_row = unit[intervention]
        base_id = str(
            baseline_row.get("base_task_id") or baseline_row["scenario_id"]
        )
        if base_id != str(
            intervention_row.get("base_task_id")
            or intervention_row["scenario_id"]
        ):
            raise ValueError("paired rows disagree on base_task_id")
        pairs.append(
            (
                base_id,
                _binary(baseline_row[metric], metric),
                _binary(intervention_row[metric], metric),
            )
        )
    if not pairs:
        raise ValueError("no complete paired condition units")

    baseline_values = [pair[1] for pair in pairs]
    intervention_values = [pair[2] for pair in pairs]
    baseline_rate = sum(baseline_values) / len(pairs)
    intervention_rate = sum(intervention_values) / len(pairs)
    absolute_difference = intervention_rate - baseline_rate
    risk_ratio = (
        intervention_rate / baseline_rate if baseline_rate > 0 else None
    )

    clusters: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for base_id, baseline_value, intervention_value in pairs:
        clusters[base_id].append((baseline_value, intervention_value))
    cluster_ids = sorted(clusters)
    rng = random.Random(seed)
    differences: list[float] = []
    risk_ratios: list[float] = []
    for _ in range(repetitions):
        sampled_pairs: list[tuple[int, int]] = []
        for cluster_id in rng.choices(cluster_ids, k=len(cluster_ids)):
            cluster_pairs = clusters[cluster_id]
            sampled_pairs.extend(
                rng.choices(cluster_pairs, k=len(cluster_pairs))
            )
        sampled_baseline = sum(item[0] for item in sampled_pairs) / len(
            sampled_pairs
        )
        sampled_intervention = sum(item[1] for item in sampled_pairs) / len(
            sampled_pairs
        )
        differences.append(sampled_intervention - sampled_baseline)
        if sampled_baseline > 0:
            risk_ratios.append(sampled_intervention / sampled_baseline)

    alpha = (1 - confidence) / 2
    cluster_differences = [
        sum(intervention_value - baseline_value for baseline_value, intervention_value in values)
        / len(values)
        for values in clusters.values()
    ]
    p_value = (
        paired_sign_flip_p_value(
            cluster_differences,
            seed=seed + 1,
            repetitions=permutation_repetitions,
        )
        if permutation_repetitions > 0
        else None
    )
    return {
        "paired_units": len(pairs),
        "base_task_clusters": len(clusters),
        "baseline_rate": baseline_rate,
        "intervention_rate": intervention_rate,
        "absolute_difference": absolute_difference,
        "absolute_difference_ci_low": _quantile(differences, alpha),
        "absolute_difference_ci_high": _quantile(differences, 1 - alpha),
        "risk_ratio": risk_ratio,
        "risk_ratio_ci_low": (
            _quantile(risk_ratios, alpha)
            if risk_ratio is not None and risk_ratios
            else None
        ),
        "risk_ratio_ci_high": (
            _quantile(risk_ratios, 1 - alpha)
            if risk_ratio is not None and risk_ratios
            else None
        ),
        "paired_sign_flip_p_value": p_value,
    }


def paired_sign_flip_p_value(
    cluster_effects: Sequence[float],
    *,
    seed: int,
    repetitions: int,
) -> float:
    """Two-sided sign-flip randomization test over independent base tasks."""

    if not cluster_effects:
        raise ValueError("cluster_effects cannot be empty")
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    observed = abs(sum(cluster_effects) / len(cluster_effects))
    tolerance = 1e-15
    if len(cluster_effects) <= 16:
        extreme = 0
        total = 0
        for signs in itertools.product((-1, 1), repeat=len(cluster_effects)):
            permuted = abs(
                sum(sign * effect for sign, effect in zip(signs, cluster_effects))
                / len(cluster_effects)
            )
            extreme += permuted + tolerance >= observed
            total += 1
        return extreme / total

    rng = random.Random(seed)
    extreme = 0
    for _ in range(repetitions):
        permuted = abs(
            sum(
                rng.choice((-1, 1)) * effect for effect in cluster_effects
            )
            / len(cluster_effects)
        )
        extreme += permuted + tolerance >= observed
    return (extreme + 1) / (repetitions + 1)


def holm_adjust(p_values: Mapping[str, float]) -> dict[str, float]:
    """Return Holm family-wise-error adjusted p-values."""

    ordered = sorted(p_values.items(), key=lambda item: item[1])
    adjusted: dict[str, float] = {}
    running = 0.0
    count = len(ordered)
    for rank, (name, p_value) in enumerate(ordered):
        if not 0 <= p_value <= 1:
            raise ValueError(f"p-value for {name!r} is outside [0, 1]")
        candidate = min(1.0, (count - rank) * p_value)
        running = max(running, candidate)
        adjusted[name] = running
    return adjusted


def agreement(
    first: Sequence[bool],
    second: Sequence[bool],
) -> dict[str, float | int | None]:
    """Calculate raw agreement and Cohen's kappa for binary labels."""

    if len(first) != len(second):
        raise ValueError("agreement vectors must have equal length")
    if not first:
        raise ValueError("agreement vectors cannot be empty")
    first_values = [bool(value) for value in first]
    second_values = [bool(value) for value in second]
    observed = sum(
        left == right for left, right in zip(first_values, second_values)
    ) / len(first_values)
    first_positive = sum(first_values) / len(first_values)
    second_positive = sum(second_values) / len(second_values)
    expected = (
        first_positive * second_positive
        + (1 - first_positive) * (1 - second_positive)
    )
    kappa = None if math.isclose(expected, 1.0) else (observed - expected) / (
        1 - expected
    )
    return {
        "n": len(first_values),
        "raw_agreement": observed,
        "cohen_kappa": kappa,
        "first_positive_rate": first_positive,
        "second_positive_rate": second_positive,
    }


def _cluster_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    clusters: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        cluster_id = str(row.get("base_task_id") or row["scenario_id"])
        clusters[cluster_id].append(row)
    return dict(clusters)


def _repeat_cell(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        row.get("provider"),
        row.get("model"),
        row["condition"],
        row["scenario_id"],
    )


def _binary(value: Any, metric: str) -> int:
    if not isinstance(value, bool):
        raise ValueError(f"{metric} must be boolean")
    return int(value)


def _validate_bootstrap(repetitions: int, confidence: float) -> None:
    if repetitions < 2:
        raise ValueError("bootstrap repetitions must be at least 2")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")


def _quantile(values: Iterable[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate a quantile of no values")
    if not 0 <= probability <= 1:
        raise ValueError("quantile probability must be in [0, 1]")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight
