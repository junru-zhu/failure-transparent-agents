"""Build a final source bundle behind the scientific publication gate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Iterable, Sequence
import zipfile

from .publication_gate import audit_final_publication
from .release import (
    DEFAULT_SOURCE_DATE_EPOCH,
    SECRET_PATTERNS,
    build_release_bundle,
    iter_public_files,
)


_PRIVATE_ENVIRONMENT_PREFIX = b"al" + b"pha"
PRIVATE_PATTERNS = {
    "private execution environment": re.compile(
        rb"(?i)\b"
        + re.escape(_PRIVATE_ENVIRONMENT_PREFIX)
        + rb"-(?:2|3)\b"
    ),
    "macOS user path": re.compile(rb"/Users/[A-Za-z0-9._-]+/"),
    "Linux user path": re.compile(rb"/home/[A-Za-z0-9._-]+/"),
    "Windows user path": re.compile(
        rb"[A-Za-z]:\\Users\\[A-Za-z0-9._ -]+\\"
    ),
    "AWS secret environment assignment": re.compile(
        rb"(?i)\bAWS_(?:SECRET_ACCESS_KEY|SESSION_TOKEN)\s*[:=]"
    ),
}


def build_final_source_bundle(
    *,
    source_root: str | Path,
    results_root: str | Path,
    first_labels_path: str | Path,
    second_labels_path: str | Path,
    approval_path: str | Path,
    output_dir: str | Path,
    source_date_epoch: int = DEFAULT_SOURCE_DATE_EPOCH,
) -> dict[str, Any]:
    """Build an exact committed source snapshot after all final gates pass."""

    root = Path(source_root).resolve()
    gate = audit_final_publication(
        source_root=root,
        results_root=results_root,
        first_labels_path=first_labels_path,
        second_labels_path=second_labels_path,
        approval_path=approval_path,
    )
    if not gate["final_publication_ready"]:
        messages = [*gate["errors"], *gate["publication_blockers"]]
        raise ValueError(
            "final publication gate failed: " + "; ".join(messages)
        )
    _require_clean_git_snapshot(root)
    _strict_scan_source(root, iter_public_files(root))
    report = build_release_bundle(
        root=root,
        output_dir=output_dir,
        require_publication_ready=True,
        source_date_epoch=source_date_epoch,
    )
    report["final_publication_gate"] = "passed"
    report["clean_git_snapshot"] = True
    report["strict_private_data_scan"] = "passed"
    return report


def _require_clean_git_snapshot(root: Path) -> None:
    git_marker = root / ".git"
    if not git_marker.exists():
        raise ValueError(
            "final source release requires a Git checkout with a .git marker"
        )
    completed = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain",
            "--untracked-files=all",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(
            "unable to verify the Git snapshot: "
            + completed.stderr.strip()
        )
    if completed.stdout.strip():
        raise ValueError(
            "final source release requires a clean, fully tracked "
            "Git snapshot"
        )


def _strict_scan_source(root: Path, files: Iterable[Path]) -> None:
    for path in files:
        relative = path.relative_to(root).as_posix()
        if path.name == "human_sample_key.jsonl":
            raise ValueError(
                f"private human sample key selected for release: {relative}"
            )
        content = path.read_bytes()
        _scan_bytes(relative, content)
        if path.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(path) as archive:
                    for name in archive.namelist():
                        if Path(name).name == "human_sample_key.jsonl":
                            raise ValueError(
                                "private human sample key inside public ZIP: "
                                f"{relative}:{name}"
                            )
                        if name.endswith("/"):
                            continue
                        _scan_bytes(
                            f"{relative}:{name}",
                            archive.read(name),
                        )
            except zipfile.BadZipFile as error:
                raise ValueError(
                    f"invalid ZIP selected for release: {relative}"
                ) from error


def _scan_bytes(description: str, content: bytes) -> None:
    for label, pattern in {**SECRET_PATTERNS, **PRIVATE_PATTERNS}.items():
        if pattern.search(content):
            raise ValueError(f"possible {label} in {description}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--first-labels", type=Path, required=True)
    parser.add_argument("--second-labels", type=Path, required=True)
    parser.add_argument(
        "--approval",
        type=Path,
        default=Path("data/publication_approval.json"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument(
        "--source-date-epoch",
        type=int,
        default=DEFAULT_SOURCE_DATE_EPOCH,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = build_final_source_bundle(
            source_root=args.root,
            results_root=args.results_root,
            first_labels_path=args.first_labels,
            second_labels_path=args.second_labels,
            approval_path=args.approval,
            output_dir=args.output_dir,
            source_date_epoch=args.source_date_epoch,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
