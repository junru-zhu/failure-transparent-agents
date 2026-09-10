"""Create a deterministic, condition-blinded human-validation sample."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
from typing import Any, Mapping, Sequence

from .analysis import load_raw_results
from .execution import file_sha256
from .labels import LABEL_NAMES
from .schema import Scenario, load_scenarios


def create_human_sample(
    *,
    raw_paths: Sequence[str | Path],
    dataset_path: str | Path,
    output_dir: str | Path,
    sample_size: int = 270,
    seed: int = 20260910,
) -> dict[str, Any]:
    """Sample successful responses and write blinded packets plus a private key."""

    if sample_size < 1:
        raise ValueError("sample_size must be positive")
    records = [
        record
        for record in load_raw_results(raw_paths)
        if record["status"] == "success"
    ]
    if sample_size > len(records):
        raise ValueError(
            f"sample_size {sample_size} exceeds {len(records)} successful responses"
        )
    scenarios = {scenario.id: scenario for scenario in load_scenarios(dataset_path)}
    missing_scenarios = {
        str(record["scenario_id"]) for record in records
    } - scenarios.keys()
    if missing_scenarios:
        raise ValueError(
            f"raw results reference {len(missing_scenarios)} unknown scenarios"
        )

    selected = stratified_sample(records, sample_size=sample_size, seed=seed)
    selected.sort(key=lambda record: str(record["response_id"]))
    packets = [
        build_blinded_packet(record, scenarios[str(record["scenario_id"])])
        for record in selected
    ]
    key = [
        {
            "response_id": record["response_id"],
            "provider": record["provider"],
            "model": record["model"],
            "condition": record["condition"],
            "category": record["category"],
            "pressure_type": record["pressure_type"],
            "scenario_id": record["scenario_id"],
            "base_task_id": record.get("base_task_id") or record["scenario_id"],
            "repeat_index": record["repeat_index"],
        }
        for record in selected
    ]

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    packet_path = destination / "human_sample_blinded.jsonl"
    key_path = destination / "human_sample_key.jsonl"
    _write_jsonl(packet_path, packets)
    _write_jsonl(key_path, key)
    stratum_counts: dict[str, int] = defaultdict(int)
    pressure_counts: dict[str, int] = defaultdict(int)
    for record in selected:
        stratum_counts[
            "|".join(
                (
                    str(record["model"]),
                    str(record["condition"]),
                    str(record["category"]),
                )
            )
        ] += 1
        pressure_counts[str(record["pressure_type"])] += 1
    manifest = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": seed,
        "sample_size": sample_size,
        "successful_population": len(records),
        "sample_fraction": sample_size / len(records),
        "stratification": [
            "model",
            "condition",
            "category",
            "pressure_type within each primary stratum",
        ],
        "blinded_fields_removed": ["provider", "model", "condition", "repeat_index"],
        "dataset": str(dataset_path),
        "dataset_sha256": file_sha256(dataset_path),
        "raw_inputs": [
            {"path": str(path), "sha256": file_sha256(path)} for path in raw_paths
        ],
        "packet": packet_path.name,
        "packet_sha256": file_sha256(packet_path),
        "private_key": key_path.name,
        "private_key_sha256": file_sha256(key_path),
        "stratum_counts": dict(sorted(stratum_counts.items())),
        "pressure_counts": dict(sorted(pressure_counts.items())),
    }
    (destination / "human_sample_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def stratified_sample(
    records: Sequence[dict[str, Any]],
    *,
    sample_size: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Allocate across model-condition-category, then pressure within stratum."""

    primary: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        primary[
            (
                str(record["model"]),
                str(record["condition"]),
                str(record["category"]),
            )
        ].append(record)
    primary_quotas = _balanced_quotas(
        {key: len(value) for key, value in primary.items()},
        total=sample_size,
        seed=seed,
    )
    pressure_capacities = Counter(
        str(record["pressure_type"]) for record in records
    )
    pressure_targets = _balanced_quotas(
        pressure_capacities,
        total=sample_size,
        seed=_derived_seed(seed, "global-pressure-targets"),
    )
    pressure_remaining = dict(pressure_targets)
    selected: list[dict[str, Any]] = []
    for primary_key in sorted(primary):
        quota = primary_quotas[primary_key]
        pressure_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in primary[primary_key]:
            pressure_groups[str(record["pressure_type"])].append(record)
        pressure_quotas = _allocate_pressure_quota(
            capacities={key: len(value) for key, value in pressure_groups.items()},
            total=quota,
            remaining_global_targets=pressure_remaining,
            seed=_derived_seed(seed, *primary_key),
        )
        for pressure in sorted(pressure_groups):
            items = sorted(
                pressure_groups[pressure],
                key=lambda record: str(record["response_id"]),
            )
            rng = random.Random(_derived_seed(seed, *primary_key, pressure))
            selected.extend(rng.sample(items, pressure_quotas[pressure]))
    if len(selected) != sample_size:
        raise AssertionError("stratified sampler returned the wrong sample size")
    selected_pressure_counts = Counter(
        str(record["pressure_type"]) for record in selected
    )
    if dict(selected_pressure_counts) != pressure_targets:
        raise AssertionError(
            "pressure-balanced sampler did not meet global targets"
        )
    return selected


def build_blinded_packet(
    record: Mapping[str, Any],
    scenario: Scenario,
) -> dict[str, Any]:
    observation = scenario.tool_observation
    return {
        "schema_version": "1.0",
        "response_id": record["response_id"],
        "scenario": {
            "user_request": scenario.user_request,
            "tool_observation": {
                "name": observation.name,
                "status": observation.status,
                "error_code": observation.error_code,
                "message": observation.message,
                "metadata": observation.metadata,
            },
            "required_evidence": list(scenario.required_evidence),
            "recovery_hint": scenario.recovery_hint,
            "safe_partial_help": scenario.safe_partial_help,
        },
        "assistant_response": record["response"],
        "annotation_template": {
            "schema_version": "1.0",
            "response_id": record["response_id"],
            "annotator_id": "",
            "annotator_type": "human",
            **{name: None for name in LABEL_NAMES},
            "evidence_spans": {name: [] for name in LABEL_NAMES},
            "confidence": None,
            "notes": "",
        },
    }


def _balanced_quotas(
    capacities: Mapping[Any, int],
    *,
    total: int,
    seed: int,
) -> dict[Any, int]:
    if total < 0 or total > sum(capacities.values()):
        raise ValueError("quota total is outside available capacity")
    keys = sorted(capacities, key=str)
    quotas = {key: 0 for key in keys}
    remaining = total
    rng = random.Random(seed)
    tie_order = keys[:]
    rng.shuffle(tie_order)
    tie_rank = {key: index for index, key in enumerate(tie_order)}
    while remaining:
        eligible = [key for key in keys if quotas[key] < capacities[key]]
        if not eligible:
            raise AssertionError("quota allocation exhausted capacity")
        eligible.sort(key=lambda key: (quotas[key], tie_rank[key], str(key)))
        for key in eligible:
            if remaining == 0:
                break
            quotas[key] += 1
            remaining -= 1
    return quotas


def _allocate_pressure_quota(
    *,
    capacities: Mapping[str, int],
    total: int,
    remaining_global_targets: dict[str, int],
    seed: int,
) -> dict[str, int]:
    if total > sum(capacities.values()):
        raise ValueError("pressure quota exceeds stratum capacity")
    keys = sorted(capacities)
    quotas = {key: 0 for key in keys}
    rng = random.Random(seed)
    tie_order = keys[:]
    rng.shuffle(tie_order)
    tie_rank = {key: index for index, key in enumerate(tie_order)}

    if total >= len(keys):
        for key in sorted(
            keys,
            key=lambda item: (
                -remaining_global_targets.get(item, 0),
                tie_rank[item],
            ),
        ):
            if capacities[key] < 1:
                continue
            quotas[key] += 1
            remaining_global_targets[key] -= 1

    while sum(quotas.values()) < total:
        eligible = [
            key
            for key in keys
            if quotas[key] < capacities[key]
            and remaining_global_targets.get(key, 0) > 0
        ]
        if not eligible:
            eligible = [
                key for key in keys if quotas[key] < capacities[key]
            ]
        if not eligible:
            raise AssertionError("pressure allocation exhausted capacity")
        eligible.sort(
            key=lambda key: (
                -remaining_global_targets.get(key, 0),
                quotas[key],
                tie_rank[key],
                key,
            )
        )
        selected = eligible[0]
        quotas[selected] += 1
        remaining_global_targets[selected] -= 1
    return quotas


def _derived_seed(seed: int, *parts: str) -> int:
    payload = "\0".join((str(seed), *parts)).encode("utf-8")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _write_jsonl(path: Path, values: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for value in values:
            handle.write(json.dumps(value, sort_keys=True) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, action="append", required=True)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/confirmatory_scenarios.jsonl"),
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=270)
    parser.add_argument("--seed", type=int, default=20260910)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manifest = create_human_sample(
        raw_paths=args.raw,
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        sample_size=args.sample_size,
        seed=args.seed,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
