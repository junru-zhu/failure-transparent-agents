"""Run a post-freeze descriptive human-label sensitivity analysis."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Any, Mapping, Sequence

from .analysis import (
    ALL_METRICS,
    INTERVENTIONS,
    PRIMARY_METRICS,
    build_agreement_report,
    build_rate_rows,
    load_raw_results,
)
from .conditions import Condition
from .execution import file_sha256
from .labels import LABEL_NAMES, ResponseLabel, load_labels


def run_human_sensitivity(
    *,
    raw_paths: Sequence[str | Path],
    human_labels_path: str | Path,
    sample_key_path: str | Path,
    sample_manifest_path: str | Path,
    output_dir: str | Path,
    bootstrap_repetitions: int = 10_000,
    seed: int = 20260910,
    model_judge_labels_path: str | Path | None = None,
    expected_sample_size: int | None = None,
) -> dict[str, Any]:
    """Analyze a human-consensus subset without requiring complete pairs."""

    if not raw_paths:
        raise ValueError("at least one raw result path is required")
    human_labels = load_labels(human_labels_path)
    _validate_human_consensus(
        human_labels,
        expected_sample_size=expected_sample_size,
    )
    human_by_id = _one_label_per_response(human_labels)
    sample_authentication = _validate_frozen_sample(
        sample_key_path=sample_key_path,
        sample_manifest_path=sample_manifest_path,
        raw_paths=raw_paths,
        human_response_ids=set(human_by_id),
        expected_sample_size=expected_sample_size,
    )

    raw = load_raw_results(raw_paths)
    successful_by_id = {
        str(record["response_id"]): record
        for record in raw
        if record["status"] == "success"
    }
    unknown = human_by_id.keys() - successful_by_id.keys()
    if unknown:
        raise ValueError(
            f"human labels contain {len(unknown)} unknown or failed responses"
        )
    sampled_rows = [
        _join_label(successful_by_id[response_id], human_by_id[response_id])
        for response_id in successful_by_id
        if response_id in human_by_id
    ]
    if len(sampled_rows) != len(human_by_id):
        raise ValueError("failed to join every human label")
    sampled_rows.sort(key=lambda row: str(row["response_id"]))

    rate_rows = build_rate_rows(
        sampled_rows,
        bootstrap_repetitions=bootstrap_repetitions,
        seed=seed,
    )
    comparison_rows: list[dict[str, Any]] = []
    for metric in PRIMARY_METRICS:
        for intervention in INTERVENTIONS:
            effect = clustered_condition_difference(
                sampled_rows,
                metric,
                baseline=Condition.BASELINE.value,
                intervention=intervention,
                repetitions=bootstrap_repetitions,
                seed=_derived_seed(seed, metric, intervention),
            )
            comparison_rows.append(
                {
                    "metric": metric,
                    "baseline_condition": Condition.BASELINE.value,
                    "intervention_condition": intervention,
                    **effect,
                    "direction_matches_expected": (
                        float(effect["absolute_difference"]) < 0
                    ),
                    "inference": "descriptive_cluster_bootstrap_no_p_value",
                }
            )

    agreement_report = None
    if model_judge_labels_path is not None:
        agreement_report = build_agreement_report(
            load_labels(model_judge_labels_path),
            human_labels,
        )
        if (
            agreement_report["shared_responses"] != len(human_labels)
            or agreement_report["human_only_responses"] != 0
        ):
            raise ValueError(
                "model-judge labels must cover every human response"
            )

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    _write_jsonl(
        destination / "human_labeled_sample.jsonl",
        sampled_rows,
    )
    _write_csv(destination / "human_rates.csv", rate_rows)
    _write_csv(
        destination / "human_primary_comparisons.csv",
        comparison_rows,
    )
    if agreement_report is not None:
        _write_json(
            destination / "model_human_agreement.json",
            agreement_report,
        )

    summary = {
        "schema_version": "1.0",
        "scientific_status": "human_validation_sensitivity",
        "analysis_status": "post_freeze_descriptive",
        "analysis_seed": seed,
        "bootstrap_repetitions": bootstrap_repetitions,
        "sampled_responses": len(sampled_rows),
        "base_task_clusters": len(
            {
                str(row.get("base_task_id") or row["scenario_id"])
                for row in sampled_rows
            }
        ),
        "models": sorted({str(row["model"]) for row in sampled_rows}),
        "conditions": sorted(
            {str(row["condition"]) for row in sampled_rows}
        ),
        "metrics": list(ALL_METRICS),
        "primary_metrics": list(PRIMARY_METRICS),
        "human_annotator_id": human_labels[0].annotator_id,
        "human_labels_path": str(human_labels_path),
        "frozen_sample_key_sha256": sample_authentication[
            "sample_key_sha256"
        ],
        "frozen_sample_manifest_sha256": sample_authentication[
            "sample_manifest_sha256"
        ],
        "frozen_sample_authenticated": True,
        "model_human_agreement_available": agreement_report is not None,
        "inference_scope": (
            "post-freeze descriptive sensitivity analysis conditional on "
            "the frozen stratified 270-response sample; intervals use a "
            "base-task cluster bootstrap, do not model the original "
            "without-replacement sampling stage, and are not confirmatory "
            "population confidence intervals; no p-values are reported"
        ),
        "all_primary_directions_match_expected": all(
            bool(row["direction_matches_expected"])
            for row in comparison_rows
        ),
        "artifacts": {
            "labeled_sample": "human_labeled_sample.jsonl",
            "rates": "human_rates.csv",
            "primary_comparisons": "human_primary_comparisons.csv",
            "model_human_agreement": (
                "model_human_agreement.json"
                if agreement_report is not None
                else None
            ),
        },
    }
    _write_json(destination / "sensitivity_summary.json", summary)
    return summary


def _validate_human_consensus(
    labels: Sequence[ResponseLabel],
    *,
    expected_sample_size: int | None,
) -> None:
    if any(label.annotator_type != "human" for label in labels):
        raise ValueError("sensitivity analysis requires human labels")
    annotator_ids = {label.annotator_id for label in labels}
    if len(annotator_ids) != 1:
        raise ValueError("human consensus must use exactly one annotator ID")
    if expected_sample_size is not None and len(labels) != expected_sample_size:
        raise ValueError(
            f"expected {expected_sample_size} human labels, found {len(labels)}"
        )
    _one_label_per_response(labels)


def _validate_frozen_sample(
    *,
    sample_key_path: str | Path,
    sample_manifest_path: str | Path,
    raw_paths: Sequence[str | Path],
    human_response_ids: set[str],
    expected_sample_size: int | None,
) -> dict[str, str]:
    key_path = Path(sample_key_path)
    manifest_path = Path(sample_manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("human sample manifest must be a JSON object")
    key_sha256 = file_sha256(key_path)
    if manifest.get("private_key_sha256") != key_sha256:
        raise ValueError("human sample key hash does not match its manifest")

    sample_ids: list[str] = []
    seen: set[str] = set()
    with key_path.open(encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            if not raw_line.strip():
                continue
            value = json.loads(raw_line)
            if not isinstance(value, dict):
                raise ValueError(
                    f"{key_path}:{line_number}: sample key row must be an object"
                )
            response_id = value.get("response_id")
            if not isinstance(response_id, str) or not response_id:
                raise ValueError(
                    f"{key_path}:{line_number}: response_id must be non-empty"
                )
            if response_id in seen:
                raise ValueError(
                    f"{key_path}:{line_number}: duplicate response_id"
                )
            seen.add(response_id)
            sample_ids.append(response_id)

    manifest_size = manifest.get("sample_size")
    if not isinstance(manifest_size, int) or manifest_size != len(sample_ids):
        raise ValueError("human sample size does not match its manifest")
    if expected_sample_size is not None and len(sample_ids) != expected_sample_size:
        raise ValueError(
            f"expected {expected_sample_size} frozen sample IDs, "
            f"found {len(sample_ids)}"
        )
    if set(sample_ids) != human_response_ids:
        missing = len(set(sample_ids) - human_response_ids)
        unexpected = len(human_response_ids - set(sample_ids))
        raise ValueError(
            "human labels do not exactly match the frozen sample: "
            f"missing={missing}, unexpected={unexpected}"
        )

    raw_inputs = manifest.get("raw_inputs")
    if not isinstance(raw_inputs, list):
        raise ValueError("human sample manifest raw_inputs must be an array")
    expected_raw_hashes = {
        item.get("sha256")
        for item in raw_inputs
        if isinstance(item, dict) and isinstance(item.get("sha256"), str)
    }
    actual_raw_hashes = {file_sha256(path) for path in raw_paths}
    if (
        len(expected_raw_hashes) != len(raw_inputs)
        or expected_raw_hashes != actual_raw_hashes
    ):
        raise ValueError(
            "raw result hashes do not match the frozen sample manifest"
        )
    return {
        "sample_key_sha256": key_sha256,
        "sample_manifest_sha256": file_sha256(manifest_path),
    }


def _one_label_per_response(
    labels: Sequence[ResponseLabel],
) -> dict[str, ResponseLabel]:
    output: dict[str, ResponseLabel] = {}
    for label in labels:
        if label.response_id in output:
            raise ValueError(
                f"multiple human labels for {label.response_id!r}"
            )
        output[label.response_id] = label
    return output


def _join_label(
    record: Mapping[str, Any],
    label: ResponseLabel,
) -> dict[str, Any]:
    return {
        **record,
        **{name: bool(getattr(label, name)) for name in LABEL_NAMES},
        "label_annotator_id": label.annotator_id,
        "label_annotator_type": label.annotator_type,
        "label_confidence": label.confidence,
        "label_evidence_spans": {
            name: list(label.evidence_spans[name]) for name in LABEL_NAMES
        },
        "label_notes": label.notes,
    }


def _derived_seed(seed: int, *parts: str) -> int:
    payload = "\0".join((str(seed), *parts)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def clustered_condition_difference(
    rows: Sequence[Mapping[str, Any]],
    metric: str,
    *,
    baseline: str,
    intervention: str,
    repetitions: int,
    seed: int,
    confidence: float = 0.95,
) -> dict[str, float | int | None]:
    """Estimate a descriptive unpaired difference with cluster bootstrap CIs."""

    if repetitions < 2:
        raise ValueError("bootstrap repetitions must be at least 2")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")
    selected = [
        row
        for row in rows
        if str(row["condition"]) in {baseline, intervention}
    ]
    baseline_values = [
        _binary(row[metric], metric)
        for row in selected
        if str(row["condition"]) == baseline
    ]
    intervention_values = [
        _binary(row[metric], metric)
        for row in selected
        if str(row["condition"]) == intervention
    ]
    if not baseline_values or not intervention_values:
        raise ValueError("both conditions require at least one sampled row")

    baseline_rate = sum(baseline_values) / len(baseline_values)
    intervention_rate = sum(intervention_values) / len(intervention_values)
    risk_ratio = (
        intervention_rate / baseline_rate if baseline_rate > 0 else None
    )
    clusters: dict[str, list[Mapping[str, Any]]] = {}
    for row in selected:
        cluster_id = str(row.get("base_task_id") or row["scenario_id"])
        clusters.setdefault(cluster_id, []).append(row)

    cluster_ids = sorted(clusters)
    rng = random.Random(seed)
    differences: list[float] = []
    risk_ratios: list[float] = []
    zero_baseline_draws = 0
    attempts = 0
    while len(differences) < repetitions:
        attempts += 1
        if attempts > repetitions * 100:
            raise ValueError(
                "cluster bootstrap repeatedly omitted a required condition"
            )
        sampled_baseline: list[int] = []
        sampled_intervention: list[int] = []
        for cluster_id in rng.choices(cluster_ids, k=len(cluster_ids)):
            for row in clusters[cluster_id]:
                condition = str(row["condition"])
                value = _binary(row[metric], metric)
                if condition == baseline:
                    sampled_baseline.append(value)
                elif condition == intervention:
                    sampled_intervention.append(value)
        if not sampled_baseline or not sampled_intervention:
            continue
        sampled_baseline_rate = sum(sampled_baseline) / len(
            sampled_baseline
        )
        sampled_intervention_rate = sum(sampled_intervention) / len(
            sampled_intervention
        )
        differences.append(
            sampled_intervention_rate - sampled_baseline_rate
        )
        if sampled_baseline_rate > 0:
            risk_ratios.append(
                sampled_intervention_rate / sampled_baseline_rate
            )
        else:
            zero_baseline_draws += 1

    alpha = (1 - confidence) / 2
    return {
        "baseline_n": len(baseline_values),
        "intervention_n": len(intervention_values),
        "base_task_clusters": len(clusters),
        "baseline_rate": baseline_rate,
        "intervention_rate": intervention_rate,
        "absolute_difference": intervention_rate - baseline_rate,
        "absolute_difference_ci_low": _quantile(differences, alpha),
        "absolute_difference_ci_high": _quantile(
            differences, 1 - alpha
        ),
        "risk_ratio": risk_ratio,
        "risk_ratio_bootstrap_zero_baseline_draws": zero_baseline_draws,
        "risk_ratio_ci_low": (
            _quantile(risk_ratios, alpha)
            if (
                risk_ratio is not None
                and risk_ratios
                and zero_baseline_draws == 0
            )
            else None
        ),
        "risk_ratio_ci_high": (
            _quantile(risk_ratios, 1 - alpha)
            if (
                risk_ratio is not None
                and risk_ratios
                and zero_baseline_draws == 0
            )
            else None
        ),
    }


def _binary(value: Any, metric: str) -> int:
    if not isinstance(value, bool):
        raise ValueError(f"{metric} must be boolean")
    return int(value)


def _quantile(values: Sequence[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot calculate a quantile of no values")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def _write_jsonl(
    path: Path,
    values: Sequence[Mapping[str, Any]],
) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True) + "\n")


def _write_csv(
    path: Path,
    rows: Sequence[Mapping[str, Any]],
) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV {path}")
    fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, action="append", required=True)
    parser.add_argument("--human-labels", type=Path, required=True)
    parser.add_argument("--sample-key", type=Path, required=True)
    parser.add_argument("--sample-manifest", type=Path, required=True)
    parser.add_argument("--model-judge-labels", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-repetitions", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260910)
    parser.add_argument("--expected-sample-size", type=int)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_human_sensitivity(
        raw_paths=args.raw,
        human_labels_path=args.human_labels,
        sample_key_path=args.sample_key,
        sample_manifest_path=args.sample_manifest,
        model_judge_labels_path=args.model_judge_labels,
        output_dir=args.output_dir,
        bootstrap_repetitions=args.bootstrap_repetitions,
        seed=args.seed,
        expected_sample_size=args.expected_sample_size,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
