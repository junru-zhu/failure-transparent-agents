"""Join labels to responses and produce reproducible statistical artifacts."""

from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import html
import json
from pathlib import Path
import statistics
from typing import Any, Iterable, Mapping, Sequence

from .conditions import Condition
from .labels import LABEL_NAMES, ResponseLabel, load_labels
from .statistics import (
    agreement,
    hierarchical_rate_interval,
    holm_adjust,
    paired_condition_effect,
)


PRIMARY_METRICS = ("false_success", "fabricated_details")
SECONDARY_METRICS = (
    "limitation_disclosed",
    "recovery_action",
    "useful_response",
    "over_refusal",
)
ALL_METRICS = PRIMARY_METRICS + SECONDARY_METRICS
INTERVENTIONS = (
    Condition.TRANSPARENCY.value,
    Condition.EVIDENCE_CONTRACT.value,
)


def run_analysis(
    *,
    raw_paths: Sequence[str | Path],
    labels_path: str | Path,
    output_dir: str | Path,
    bootstrap_repetitions: int = 10_000,
    permutation_repetitions: int = 100_000,
    seed: int = 20260910,
    model_judge_labels_path: str | Path | None = None,
    human_labels_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run the frozen analysis and write all machine-readable/report artifacts."""

    if not raw_paths:
        raise ValueError("at least one raw result path is required")
    raw = load_raw_results(raw_paths)
    successful = [record for record in raw if record["status"] == "success"]
    provider_errors = [
        record for record in raw if record["status"] == "provider_error"
    ]
    labels = _one_label_per_response(load_labels(labels_path), "analysis labels")
    labeled_rows = join_labels(successful, labels)

    rate_rows = build_rate_rows(
        labeled_rows,
        bootstrap_repetitions=bootstrap_repetitions,
        seed=seed,
    )
    comparison_rows = build_comparison_rows(
        labeled_rows,
        bootstrap_repetitions=bootstrap_repetitions,
        permutation_repetitions=permutation_repetitions,
        seed=seed,
    )
    efficiency_rows = build_efficiency_rows(successful)

    agreement_result = None
    if (model_judge_labels_path is None) != (human_labels_path is None):
        raise ValueError(
            "model-judge and human label paths must be supplied together"
        )
    if model_judge_labels_path is not None and human_labels_path is not None:
        agreement_result = build_agreement_report(
            load_labels(model_judge_labels_path),
            load_labels(human_labels_path),
        )

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    _write_jsonl(destination / "labeled_results.jsonl", labeled_rows)
    _write_csv(destination / "rates.csv", rate_rows)
    _write_csv(destination / "comparisons.csv", comparison_rows)
    _write_csv(destination / "efficiency.csv", efficiency_rows)
    if agreement_result is not None:
        _write_json(destination / "agreement.json", agreement_result)

    figures = destination / "figures"
    figures.mkdir(exist_ok=True)
    _write_figure_false_success(
        figures / "figure1_false_success_by_model.svg",
        rate_rows,
    )
    _write_figure_secondary(
        figures / "figure2_transparency_and_utility.svg",
        rate_rows,
    )
    _write_figure_pressure(
        figures / "figure3_pressure_ablation.svg",
        rate_rows,
    )
    tables = destination / "tables"
    tables.mkdir(exist_ok=True)
    _write_ablation_table(tables / "ablation_table.tex", rate_rows)

    summary = {
        "schema_version": "1.0",
        "analysis_seed": seed,
        "bootstrap_repetitions": bootstrap_repetitions,
        "permutation_repetitions": permutation_repetitions,
        "raw_records": len(raw),
        "successful_responses": len(successful),
        "provider_errors": len(provider_errors),
        "labeled_responses": len(labeled_rows),
        "base_task_clusters": len(
            {str(row.get("base_task_id") or row["scenario_id"]) for row in labeled_rows}
        ),
        "task_instances": len({str(row["scenario_id"]) for row in labeled_rows}),
        "models": sorted({str(row["model"]) for row in labeled_rows}),
        "conditions": sorted({str(row["condition"]) for row in labeled_rows}),
        "primary_metrics": list(PRIMARY_METRICS),
        "secondary_metrics": list(SECONDARY_METRICS),
        "cluster_unit": "base_task_id",
        "repeat_resampling_unit": "provider-model-condition-scenario",
        "main_label_source": str(labels_path),
        "agreement_available": agreement_result is not None,
        "artifacts": {
            "labeled_results": "labeled_results.jsonl",
            "rates": "rates.csv",
            "comparisons": "comparisons.csv",
            "efficiency": "efficiency.csv",
            "agreement": "agreement.json" if agreement_result is not None else None,
            "figures": [
                "figures/figure1_false_success_by_model.svg",
                "figures/figure2_transparency_and_utility.svg",
                "figures/figure3_pressure_ablation.svg",
            ],
            "ablation_table": "tables/ablation_table.tex",
        },
    }
    _write_json(destination / "analysis_summary.json", summary)
    return summary


def load_raw_results(paths: Sequence[str | Path]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_path in paths:
        path = Path(raw_path)
        with path.open(encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                if not raw_line.strip():
                    continue
                value = json.loads(raw_line)
                if not isinstance(value, dict):
                    raise ValueError(f"{path}:{line_number}: record must be an object")
                response_id = value.get("response_id")
                if not isinstance(response_id, str) or not response_id:
                    raise ValueError(
                        f"{path}:{line_number}: response_id must be non-empty"
                    )
                if response_id in seen:
                    raise ValueError(
                        f"{path}:{line_number}: duplicate response_id {response_id!r}"
                    )
                if value.get("status") not in {"success", "provider_error"}:
                    raise ValueError(
                        f"{path}:{line_number}: unsupported status"
                    )
                seen.add(response_id)
                records.append(value)
    if not records:
        raise ValueError("no raw result records found")
    return records


def join_labels(
    successful_records: Sequence[dict[str, Any]],
    labels: Mapping[str, ResponseLabel],
) -> list[dict[str, Any]]:
    expected = {str(record["response_id"]) for record in successful_records}
    missing = expected - labels.keys()
    unexpected = labels.keys() - expected
    if missing:
        raise ValueError(
            f"missing labels for {len(missing)} successful responses"
        )
    if unexpected:
        raise ValueError(f"labels contain {len(unexpected)} unknown response IDs")
    joined: list[dict[str, Any]] = []
    for record in successful_records:
        label = labels[str(record["response_id"])]
        joined.append(
            {
                **record,
                **{name: getattr(label, name) for name in LABEL_NAMES},
                "label_annotator_id": label.annotator_id,
                "label_annotator_type": label.annotator_type,
                "label_confidence": label.confidence,
                "label_evidence_spans": {
                    name: list(label.evidence_spans[name]) for name in LABEL_NAMES
                },
                "label_notes": label.notes,
            }
        )
    return joined


def build_rate_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_repetitions: int,
    seed: int,
) -> list[dict[str, Any]]:
    specifications: list[tuple[str, tuple[str, ...]]] = [
        ("overall", ("condition",)),
        ("model", ("model", "condition")),
        ("category", ("category", "condition")),
        ("pressure", ("pressure_type", "condition")),
    ]
    output: list[dict[str, Any]] = []
    for scope, fields in specifications:
        groups: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
        for row in rows:
            groups[tuple(str(row[field]) for field in fields)].append(row)
        for key, group_rows in sorted(groups.items()):
            dimensions = dict(zip(fields, key))
            for metric in ALL_METRICS:
                interval = hierarchical_rate_interval(
                    group_rows,
                    metric,
                    repetitions=bootstrap_repetitions,
                    seed=_derived_seed(seed, scope, *key, metric),
                )
                output.append(
                    {
                        "scope": scope,
                        "model": dimensions.get("model", "all"),
                        "category": dimensions.get("category", "all"),
                        "pressure_type": dimensions.get("pressure_type", "all"),
                        "condition": dimensions["condition"],
                        "metric": metric,
                        **interval,
                    }
                )
    return output


def build_comparison_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    bootstrap_repetitions: int,
    permutation_repetitions: int,
    seed: int,
) -> list[dict[str, Any]]:
    scopes: list[tuple[str, str, list[Mapping[str, Any]]]] = [
        ("overall", "all", list(rows))
    ]
    models = sorted({str(row["model"]) for row in rows})
    for model in models:
        scopes.append(
            (
                "model",
                model,
                [row for row in rows if str(row["model"]) == model],
            )
        )

    output: list[dict[str, Any]] = []
    raw_primary_p_values: dict[str, float] = {}
    for scope, scope_value, scope_rows in scopes:
        for metric in ALL_METRICS:
            for intervention in INTERVENTIONS:
                is_primary_test = (
                    scope == "overall" and metric in PRIMARY_METRICS
                )
                effect = paired_condition_effect(
                    scope_rows,
                    metric,
                    baseline=Condition.BASELINE.value,
                    intervention=intervention,
                    repetitions=bootstrap_repetitions,
                    seed=_derived_seed(
                        seed,
                        "comparison",
                        scope,
                        scope_value,
                        metric,
                        intervention,
                    ),
                    permutation_repetitions=(
                        permutation_repetitions if is_primary_test else 0
                    ),
                )
                test_id = f"{scope}:{scope_value}:{metric}:{intervention}"
                row = {
                    "test_id": test_id,
                    "scope": scope,
                    "scope_value": scope_value,
                    "metric": metric,
                    "baseline_condition": Condition.BASELINE.value,
                    "intervention_condition": intervention,
                    **effect,
                    "holm_adjusted_p_value": None,
                }
                output.append(row)
                if is_primary_test:
                    raw_primary_p_values[test_id] = float(
                        effect["paired_sign_flip_p_value"]
                    )

    adjusted = holm_adjust(raw_primary_p_values)
    for row in output:
        if row["test_id"] in adjusted:
            row["holm_adjusted_p_value"] = adjusted[row["test_id"]]
    return output


def build_efficiency_rows(
    successful_records: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for record in successful_records:
        groups[(str(record["model"]), str(record["condition"]))].append(record)
    output: list[dict[str, Any]] = []
    for (model, condition), records in sorted(groups.items()):
        usages = [record["usage"] for record in records]
        costs = [
            float(usage["estimated_cost_usd"])
            for usage in usages
            if usage.get("estimated_cost_usd") is not None
        ]
        latencies = [int(usage["latency_ms"]) for usage in usages]
        output.append(
            {
                "model": model,
                "condition": condition,
                "responses": len(records),
                "input_tokens": sum(int(usage["input_tokens"]) for usage in usages),
                "cached_input_tokens": sum(
                    int(usage.get("cached_input_tokens", 0)) for usage in usages
                ),
                "reasoning_tokens": sum(
                    int(usage.get("reasoning_tokens", 0)) for usage in usages
                ),
                "output_tokens": sum(
                    int(usage["output_tokens"]) for usage in usages
                ),
                "estimated_cost_usd": (
                    sum(costs) if len(costs) == len(usages) else None
                ),
                "median_latency_ms": statistics.median(latencies),
                "p95_latency_ms": _percentile(latencies, 0.95),
            }
        )
    return output


def build_agreement_report(
    model_labels: Sequence[ResponseLabel],
    human_labels: Sequence[ResponseLabel],
) -> dict[str, Any]:
    model_by_id = _one_label_per_response(model_labels, "model-judge labels")
    human_by_id = _one_label_per_response(human_labels, "human labels")
    shared = sorted(model_by_id.keys() & human_by_id.keys())
    if not shared:
        raise ValueError("model-judge and human labels do not overlap")
    metrics = {
        metric: agreement(
            [getattr(model_by_id[identifier], metric) for identifier in shared],
            [getattr(human_by_id[identifier], metric) for identifier in shared],
        )
        for metric in ALL_METRICS
    }
    return {
        "schema_version": "1.0",
        "shared_responses": len(shared),
        "model_only_responses": len(model_by_id.keys() - human_by_id.keys()),
        "human_only_responses": len(human_by_id.keys() - model_by_id.keys()),
        "metrics": metrics,
    }


def _one_label_per_response(
    labels: Sequence[ResponseLabel],
    label: str,
) -> dict[str, ResponseLabel]:
    by_id: dict[str, ResponseLabel] = {}
    for item in labels:
        if item.response_id in by_id:
            raise ValueError(
                f"{label} contain multiple annotations for {item.response_id!r}"
            )
        by_id[item.response_id] = item
    return by_id


def _write_figure_false_success(
    path: Path,
    rate_rows: Sequence[Mapping[str, Any]],
) -> None:
    selected = [
        row
        for row in rate_rows
        if row["scope"] == "model" and row["metric"] == "false_success"
    ]
    models = sorted({str(row["model"]) for row in selected})
    _write_grouped_bar_svg(
        path,
        title="False-success rate by model and instruction condition",
        x_groups=models,
        series=list(condition.value for condition in Condition),
        value_lookup={
            (str(row["model"]), str(row["condition"])): float(row["rate"])
            for row in selected
        },
        interval_lookup={
            (str(row["model"]), str(row["condition"])): (
                float(row["ci_low"]),
                float(row["ci_high"]),
            )
            for row in selected
        },
        y_label="False-success rate",
    )


def _write_figure_secondary(
    path: Path,
    rate_rows: Sequence[Mapping[str, Any]],
) -> None:
    metrics = (
        "limitation_disclosed",
        "recovery_action",
        "useful_response",
        "over_refusal",
    )
    selected = [
        row
        for row in rate_rows
        if row["scope"] == "overall" and row["metric"] in metrics
    ]
    _write_grouped_bar_svg(
        path,
        title="Transparency, recovery, usefulness, and over-refusal",
        x_groups=list(metrics),
        series=list(condition.value for condition in Condition),
        value_lookup={
            (str(row["metric"]), str(row["condition"])): float(row["rate"])
            for row in selected
        },
        interval_lookup={
            (str(row["metric"]), str(row["condition"])): (
                float(row["ci_low"]),
                float(row["ci_high"]),
            )
            for row in selected
        },
        y_label="Response rate",
    )


def _write_figure_pressure(
    path: Path,
    rate_rows: Sequence[Mapping[str, Any]],
) -> None:
    selected = [
        row
        for row in rate_rows
        if row["scope"] == "pressure" and row["metric"] == "false_success"
    ]
    pressures = sorted({str(row["pressure_type"]) for row in selected})
    _write_grouped_bar_svg(
        path,
        title="False-success rate by pressure type (descriptive)",
        x_groups=pressures,
        series=list(condition.value for condition in Condition),
        value_lookup={
            (str(row["pressure_type"]), str(row["condition"])): float(row["rate"])
            for row in selected
        },
        interval_lookup={
            (str(row["pressure_type"]), str(row["condition"])): (
                float(row["ci_low"]),
                float(row["ci_high"]),
            )
            for row in selected
        },
        y_label="False-success rate",
    )


def _write_grouped_bar_svg(
    path: Path,
    *,
    title: str,
    x_groups: Sequence[str],
    series: Sequence[str],
    value_lookup: Mapping[tuple[str, str], float],
    interval_lookup: Mapping[tuple[str, str], tuple[float, float]] | None,
    y_label: str,
) -> None:
    width, height = 960, 540
    left, right, top, bottom = 80, 30, 70, 125
    plot_width = width - left - right
    plot_height = height - top - bottom
    colors = ("#4C78A8", "#F58518", "#54A24B", "#E45756")
    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        f"<title id=\"title\">{html.escape(title)}</title>",
        f"<desc id=\"desc\">Grouped bar chart with rates from zero to one.</desc>",
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width / 2}" y="32" text-anchor="middle" '
        'font-family="sans-serif" font-size="20" font-weight="600">'
        f"{html.escape(title)}</text>",
    ]
    for tick in range(6):
        value = tick / 5
        y = top + plot_height * (1 - value)
        pieces.extend(
            [
                f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" '
                'stroke="#dddddd" stroke-width="1"/>',
                f'<text x="{left-10}" y="{y+4:.1f}" text-anchor="end" '
                'font-family="sans-serif" font-size="12">'
                f"{value:.1f}</text>",
            ]
        )
    group_width = plot_width / max(1, len(x_groups))
    bar_gap = 3
    bar_width = min(
        34,
        max(8, (group_width * 0.78 - bar_gap * (len(series) - 1)) / len(series)),
    )
    for group_index, group in enumerate(x_groups):
        center = left + group_width * (group_index + 0.5)
        total_width = len(series) * bar_width + (len(series) - 1) * bar_gap
        start = center - total_width / 2
        for series_index, series_name in enumerate(series):
            value = max(0.0, min(1.0, value_lookup.get((group, series_name), 0.0)))
            bar_height = value * plot_height
            x = start + series_index * (bar_width + bar_gap)
            y = top + plot_height - bar_height
            pieces.extend(
                [
                    f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" '
                    f'height="{bar_height:.1f}" fill="{colors[series_index % len(colors)]}"/>',
                    f'<text x="{x + bar_width / 2:.1f}" y="{max(top + 11, y - 4):.1f}" '
                    'text-anchor="middle" font-family="sans-serif" font-size="10">'
                    f"{value:.2f}</text>",
                ]
            )
            if interval_lookup is not None and (group, series_name) in interval_lookup:
                low, high = interval_lookup[(group, series_name)]
                low = max(0.0, min(1.0, low))
                high = max(0.0, min(1.0, high))
                error_x = x + bar_width / 2
                high_y = top + plot_height * (1 - high)
                low_y = top + plot_height * (1 - low)
                pieces.extend(
                    [
                        f'<line x1="{error_x:.1f}" y1="{high_y:.1f}" '
                        f'x2="{error_x:.1f}" y2="{low_y:.1f}" '
                        'stroke="#222222" stroke-width="1.5"/>',
                        f'<line x1="{error_x-4:.1f}" y1="{high_y:.1f}" '
                        f'x2="{error_x+4:.1f}" y2="{high_y:.1f}" '
                        'stroke="#222222" stroke-width="1.5"/>',
                        f'<line x1="{error_x-4:.1f}" y1="{low_y:.1f}" '
                        f'x2="{error_x+4:.1f}" y2="{low_y:.1f}" '
                        'stroke="#222222" stroke-width="1.5"/>',
                    ]
                )
        pieces.append(
            f'<text x="{center:.1f}" y="{top + plot_height + 22}" '
            'text-anchor="middle" font-family="sans-serif" font-size="11">'
            f"{html.escape(group.replace('_', ' '))}</text>"
        )
    pieces.append(
        f'<text x="18" y="{top + plot_height / 2}" text-anchor="middle" '
        f'transform="rotate(-90 18 {top + plot_height / 2})" '
        'font-family="sans-serif" font-size="13">'
        f"{html.escape(y_label)}</text>"
    )
    legend_y = height - 44
    legend_start = max(80, width / 2 - len(series) * 110)
    for index, series_name in enumerate(series):
        x = legend_start + index * 220
        pieces.extend(
            [
                f'<rect x="{x}" y="{legend_y-11}" width="14" height="14" '
                f'fill="{colors[index % len(colors)]}"/>',
                f'<text x="{x+21}" y="{legend_y}" font-family="sans-serif" '
                f'font-size="12">{html.escape(series_name.replace("_", " "))}</text>',
            ]
        )
    pieces.append("</svg>")
    path.write_text("\n".join(pieces) + "\n", encoding="utf-8")


def _write_ablation_table(
    path: Path,
    rate_rows: Sequence[Mapping[str, Any]],
) -> None:
    selected = [
        row
        for row in rate_rows
        if row["scope"] == "pressure"
        and row["metric"] in {"false_success", "useful_response"}
    ]
    lookup = {
        (
            str(row["pressure_type"]),
            str(row["condition"]),
            str(row["metric"]),
        ): row
        for row in selected
    }
    pressures = sorted({str(row["pressure_type"]) for row in selected})
    lines = [
        r"\begin{tabular}{llrrrr}",
        r"\toprule",
        r"Pressure & Condition & False success & 95\% CI & Useful & 95\% CI \\",
        r"\midrule",
    ]
    for pressure in pressures:
        for condition in (item.value for item in Condition):
            false_success = lookup[(pressure, condition, "false_success")]
            useful = lookup[(pressure, condition, "useful_response")]
            lines.append(
                "{} & {} & {:.3f} & [{:.3f}, {:.3f}] & {:.3f} & [{:.3f}, {:.3f}] \\\\".format(
                    _latex_escape(pressure),
                    _latex_escape(condition),
                    float(false_success["rate"]),
                    float(false_success["ci_low"]),
                    float(false_success["ci_high"]),
                    float(useful["rate"]),
                    float(useful["ci_low"]),
                    float(useful["ci_high"]),
                )
            )
    lines.extend((r"\bottomrule", r"\end{tabular}"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, values: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True) + "\n")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV {path}")
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _derived_seed(seed: int, *parts: str) -> int:
    payload = "\0".join((str(seed), *parts)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _percentile(values: Sequence[int], probability: float) -> int:
    ordered = sorted(values)
    index = min(
        len(ordered) - 1,
        max(0, round((len(ordered) - 1) * probability)),
    )
    return ordered[index]


def _latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "_": r"\_",
        "&": r"\&",
        "%": r"\%",
        "#": r"\#",
    }
    return "".join(replacements.get(character, character) for character in value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, action="append", required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model-judge-labels", type=Path)
    parser.add_argument("--human-labels", type=Path)
    parser.add_argument("--bootstrap-repetitions", type=int, default=10_000)
    parser.add_argument("--permutation-repetitions", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=20260910)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = run_analysis(
        raw_paths=args.raw,
        labels_path=args.labels,
        output_dir=args.output_dir,
        bootstrap_repetitions=args.bootstrap_repetitions,
        permutation_repetitions=args.permutation_repetitions,
        seed=args.seed,
        model_judge_labels_path=args.model_judge_labels,
        human_labels_path=args.human_labels,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
