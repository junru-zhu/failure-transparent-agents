"""Apply audited exact evidence spans without changing judge booleans."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from failure_transparent_agents.analysis import load_raw_results
from failure_transparent_agents.judge import parse_judge_label


def write_jsonl(path: Path, rows: list[dict]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", action="append", type=Path, required=True)
    parser.add_argument("--judge-dir", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--annotator-id", required=True)
    args = parser.parse_args()

    records = load_raw_results(args.raw)
    record_by_id = {str(row["response_id"]): row for row in records}
    progress_path = args.judge_dir / "judge_progress.jsonl"
    progress = [
        json.loads(line)
        for line in progress_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    progress_by_id = {str(row["response_id"]): row for row in progress}
    audit = json.loads(args.audit.read_text(encoding="utf-8"))["records"]

    for response_id, corrected_spans in audit.items():
        row = progress_by_id[response_id]
        raw_output = row["calls"][-1]["raw_output"]
        value = json.loads(raw_output)
        booleans_before = {
            key: value[key]
            for key in (
                "false_success",
                "fabricated_details",
                "limitation_disclosed",
                "recovery_action",
                "useful_response",
                "over_refusal",
            )
        }
        for key, spans in corrected_spans.items():
            value["evidence_spans"][key] = spans
        label = parse_judge_label(
            json.dumps(value),
            response_id=response_id,
            annotator_id=args.annotator_id,
            assistant_response=str(record_by_id[response_id]["response"]),
        )
        booleans_after = {
            key: getattr(label, key) for key in booleans_before
        }
        if booleans_after != booleans_before:
            raise ValueError(f"{response_id}: outcome booleans changed")
        progress_by_id[response_id] = {
            **row,
            "status": "success",
            "label": label.to_dict(),
            "error": None,
            "exact_span_audit": True,
        }

    ordered = [progress_by_id[str(row["response_id"])] for row in records]
    if any(row.get("status") != "success" for row in ordered):
        raise ValueError("unresolved judge rows remain")
    write_jsonl(progress_path, ordered)
    write_jsonl(
        args.judge_dir / "model_judge_labels.jsonl",
        [row["label"] for row in ordered],
    )
    print(json.dumps({"audited_rows": len(audit), "labels": len(ordered)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
