"""Deterministic release audit and source-bundle builder."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from typing import Any, Iterable
import zipfile

from .model_verification import validate_model_verification
from .schema import load_scenarios


DEFAULT_SOURCE_DATE_EPOCH = 315532800  # 1980-01-01T00:00:00Z
PUBLIC_ROOT_FILES = {
    ".gitignore",
    ".zenodo.json",
    "CITATION.cff",
    "CHANGELOG.md",
    "LICENSE",
    "Makefile",
    "README.md",
    "pyproject.toml",
}
PUBLIC_DIRECTORIES = {
    ".github",
    "configs",
    "data",
    "docs",
    "paper",
    "schemas",
    "scripts",
    "src",
    "tests",
}
EXCLUDED_PARTS = {
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    "results",
}
EXCLUDED_SUFFIXES = {
    ".aux",
    ".bbl",
    ".blg",
    ".log",
    ".out",
    ".pyc",
    ".pyo",
}
SECRET_PATTERNS = {
    "aws access-key identifier": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "GitHub personal-access token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    "OpenAI-style secret key": re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    "private key": re.compile(
        rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    "Slack token": re.compile(rb"xox[baprs]-[A-Za-z0-9-]{20,}"),
}


def sha256_bytes(value: bytes) -> str:
    """Return a lowercase SHA-256 digest."""

    return hashlib.sha256(value).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Hash one file without loading it all into memory."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    """Encode stable, human-readable JSON with one trailing newline."""

    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def iter_public_files(root: str | Path) -> list[Path]:
    """Return the allowlisted public source files in stable order."""

    source_root = Path(root).resolve()
    files: set[Path] = set()
    for relative in PUBLIC_ROOT_FILES:
        path = source_root / relative
        if path.is_file():
            files.add(path)
    for directory in PUBLIC_DIRECTORIES:
        base = source_root / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(source_root)
            if _excluded(relative):
                continue
            files.add(path)
    return sorted(files, key=lambda path: path.relative_to(source_root).as_posix())


def _excluded(relative: Path) -> bool:
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return True
    if any(part.endswith(".egg-info") for part in relative.parts):
        return True
    if relative.name == ".DS_Store":
        return True
    return relative.suffix.lower() in EXCLUDED_SUFFIXES


def audit_release(root: str | Path) -> dict[str, Any]:
    """Audit local release inputs without mutating the repository."""

    source_root = Path(root).resolve()
    errors: list[str] = []
    publication_blockers: list[str] = []
    post_publication_actions: list[str] = []

    required = sorted(PUBLIC_ROOT_FILES | PUBLIC_DIRECTORIES)
    for relative in required:
        if not (source_root / relative).exists():
            errors.append(f"missing required release path: {relative}")

    pyproject_path = source_root / "pyproject.toml"
    try:
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        project = pyproject["project"]
        project_name = _nonempty(project.get("name"), "project.name")
        version = _nonempty(project.get("version"), "project.version")
        authors = [
            _nonempty(item.get("name"), "project.authors[].name")
            for item in project.get("authors", [])
            if isinstance(item, dict)
        ]
        if not authors:
            errors.append("pyproject.toml must declare at least one author")
    except (KeyError, OSError, ValueError, tomllib.TOMLDecodeError) as error:
        errors.append(f"invalid pyproject.toml: {error}")
        project = {}
        project_name = "failure-transparent-agents"
        version = "unknown"
        authors = []

    cff_path = source_root / "CITATION.cff"
    cff_text = _read_text(cff_path, errors)
    cff_version = _cff_scalar(cff_text, "version")
    cff_license = _cff_scalar(cff_text, "license")
    cff_author = _cff_author(cff_text)
    if cff_version != version:
        errors.append(
            f"CITATION.cff version {cff_version!r} does not match {version!r}"
        )
    if cff_license != "MIT":
        errors.append("CITATION.cff license must be MIT")
    if authors and cff_author != authors[0]:
        errors.append(
            f"CITATION.cff author {cff_author!r} does not match {authors[0]!r}"
        )

    zenodo_path = source_root / ".zenodo.json"
    zenodo = _read_json_object(zenodo_path, errors)
    if zenodo.get("version") != version:
        errors.append(
            f".zenodo.json version {zenodo.get('version')!r} "
            f"does not match {version!r}"
        )
    if zenodo.get("license") != "MIT":
        errors.append(".zenodo.json license must be MIT")
    zenodo_author = _zenodo_author(zenodo)
    if authors and zenodo_author != authors[0]:
        errors.append(
            f".zenodo.json author {zenodo_author!r} does not match {authors[0]!r}"
        )

    package_version = _package_version(
        source_root / "src" / "failure_transparent_agents" / "__init__.py"
    )
    if package_version != version:
        errors.append(
            f"package version {package_version!r} does not match {version!r}"
        )
    release_notes_path = source_root / "docs" / f"release_notes-v{version}.md"
    if not release_notes_path.is_file():
        errors.append(
            f"missing versioned release notes: "
            f"docs/release_notes-v{version}.md"
        )

    dataset_path = source_root / "data" / "confirmatory_scenarios.jsonl"
    dataset_manifest = _read_json_object(
        source_root / "data" / "confirmatory_manifest.json",
        errors,
    )
    try:
        scenarios = load_scenarios(dataset_path)
    except (OSError, ValueError) as error:
        errors.append(f"invalid confirmatory dataset: {error}")
        scenarios = []
    if len(scenarios) != 100:
        errors.append(f"confirmatory dataset has {len(scenarios)} rows, expected 100")
    if dataset_path.is_file():
        dataset_sha256 = sha256_file(dataset_path)
        if dataset_manifest.get("dataset_sha256") != dataset_sha256:
            errors.append("confirmatory dataset hash does not match its manifest")
    else:
        dataset_sha256 = None
    if dataset_manifest.get("scenario_count") != 100:
        errors.append("confirmatory manifest scenario_count must be 100")

    approval = _read_json_object(
        source_root / "data" / "confirmatory_approval.json",
        errors,
    )
    if approval.get("status") != "approved":
        publication_blockers.append("collection approval is not approved")
    if approval.get("data_collection_authorized") is not True:
        publication_blockers.append("confirmatory data collection is not authorized")
    if dataset_manifest.get("frozen") is not True:
        publication_blockers.append("confirmatory dataset manifest is not frozen")
    signed_by = dataset_manifest.get("signed_by")
    if not isinstance(signed_by, str) or not signed_by.strip():
        publication_blockers.append("confirmatory manifest has no author signoff")

    verification_path = source_root / "data" / "model_verification.json"
    try:
        model_verification = validate_model_verification(
            verification_path,
            provider_config_paths=sorted(
                (source_root / "configs" / "providers").glob("*.json")
            ),
            judge_config_paths=sorted(
                (source_root / "configs" / "judges").glob("*.json")
            ),
        )
    except ValueError as error:
        errors.append(f"invalid model verification: {error}")
        model_verification = {
            "sha256": (
                sha256_file(verification_path)
                if verification_path.is_file()
                else None
            ),
            "verified_at": None,
            "ready": False,
        }

    project_urls = project.get("urls", {}) if isinstance(project, dict) else {}
    repository_url = None
    if isinstance(project_urls, dict):
        for key in ("Repository", "Source", "Homepage"):
            value = project_urls.get(key)
            if isinstance(value, str) and value.strip():
                repository_url = value.strip()
                break
    if repository_url is None:
        publication_blockers.append("public repository URL has not been selected")
    if _cff_scalar(cff_text, "repository-code") is None:
        publication_blockers.append("CITATION.cff has no repository-code URL")

    if _cff_scalar(cff_text, "doi") is None:
        post_publication_actions.append("insert the Zenodo DOI into CITATION.cff")
    readme_text = _read_text(source_root / "README.md", errors)
    if "doi.org/" not in readme_text.lower():
        post_publication_actions.append("insert the Zenodo DOI into README.md")
    paper_text = _read_text(source_root / "paper" / "main.tex", errors)
    if "doi.org/" not in paper_text.lower():
        post_publication_actions.append("insert the Zenodo DOI into paper/main.tex")

    files = iter_public_files(source_root)
    if not files:
        errors.append("release allowlist selected no files")
    secret_findings = scan_for_secrets(source_root, files)
    errors.extend(secret_findings)
    file_records = [
        {
            "path": path.relative_to(source_root).as_posix(),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in files
    ]

    return {
        "schema_version": "1.0",
        "project_name": project_name,
        "version": version,
        "authors": authors,
        "dataset_rows": len(scenarios),
        "dataset_sha256": dataset_sha256,
        "model_verification_sha256": model_verification.get("sha256"),
        "model_verification_verified_at": model_verification.get("verified_at"),
        "model_verification_ready": model_verification.get("ready", False),
        "file_count": len(file_records),
        "files": file_records,
        "errors": sorted(set(errors)),
        "publication_blockers": sorted(set(publication_blockers)),
        "post_publication_actions": sorted(set(post_publication_actions)),
        "local_release_ready": not errors,
        "publication_ready": not errors and not publication_blockers,
    }


def scan_for_secrets(root: Path, files: Iterable[Path]) -> list[str]:
    """Scan public text inputs for common credential shapes."""

    findings: list[str] = []
    for path in files:
        if path.suffix.lower() in {".pdf", ".zip"}:
            continue
        try:
            content = path.read_bytes()
        except OSError as error:
            findings.append(
                f"unable to scan {path.relative_to(root).as_posix()}: {error}"
            )
            continue
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                findings.append(
                    f"possible {label} in {path.relative_to(root).as_posix()}"
                )
    return findings


def build_release_bundle(
    *,
    root: str | Path,
    output_dir: str | Path,
    require_publication_ready: bool = False,
    source_date_epoch: int = DEFAULT_SOURCE_DATE_EPOCH,
) -> dict[str, Any]:
    """Build a deterministic, hash-addressed source archive."""

    source_root = Path(root).resolve()
    audit = audit_release(source_root)
    if audit["errors"]:
        raise ValueError("release audit failed: " + "; ".join(audit["errors"]))
    if require_publication_ready and audit["publication_blockers"]:
        raise ValueError(
            "release is not publication-ready: "
            + "; ".join(audit["publication_blockers"])
        )
    if source_date_epoch < DEFAULT_SOURCE_DATE_EPOCH:
        raise ValueError(
            f"source_date_epoch must be at least {DEFAULT_SOURCE_DATE_EPOCH}"
        )

    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    archive_stem = f"{audit['project_name']}-{audit['version']}"
    suffix = "release" if require_publication_ready else "release-candidate"
    archive_path = destination / f"{archive_stem}-{suffix}.zip"
    prefix = f"{archive_stem}/"

    embedded_manifest = {
        key: audit[key]
        for key in (
            "schema_version",
            "project_name",
            "version",
            "authors",
            "dataset_rows",
            "dataset_sha256",
            "model_verification_sha256",
            "model_verification_verified_at",
            "model_verification_ready",
            "file_count",
            "files",
            "publication_blockers",
            "post_publication_actions",
            "local_release_ready",
            "publication_ready",
        )
    }
    embedded_manifest["archive_prefix"] = prefix
    embedded_manifest["source_date_epoch"] = source_date_epoch
    manifest_bytes = canonical_json(embedded_manifest)

    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        strict_timestamps=True,
    ) as archive:
        for record in audit["files"]:
            relative = record["path"]
            content = (source_root / relative).read_bytes()
            archive.writestr(
                _zip_info(prefix + relative, source_date_epoch),
                content,
            )
        archive.writestr(
            _zip_info(prefix + "release-manifest.json", source_date_epoch),
            manifest_bytes,
        )

    archive_sha256 = sha256_file(archive_path)
    checksum_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
    checksum_path.write_text(
        f"{archive_sha256}  {archive_path.name}\n",
        encoding="utf-8",
    )
    report = {
        "schema_version": "1.0",
        "archive": str(archive_path),
        "archive_sha256": archive_sha256,
        "archive_size_bytes": archive_path.stat().st_size,
        "checksum_file": str(checksum_path),
        "embedded_manifest_sha256": sha256_bytes(manifest_bytes),
        "file_count": audit["file_count"] + 1,
        "local_release_ready": audit["local_release_ready"],
        "publication_ready": audit["publication_ready"],
        "publication_blockers": audit["publication_blockers"],
        "post_publication_actions": audit["post_publication_actions"],
        "source_date_epoch": source_date_epoch,
    }
    report_path = destination / f"{archive_stem}-release-report.json"
    report_path.write_bytes(canonical_json(report))
    report["report"] = str(report_path)
    return report


def build_wheel_from_release_archive(
    *,
    archive_path: str | Path,
    output_dir: str | Path,
    python_executable: str = sys.executable,
    source_date_epoch: int = DEFAULT_SOURCE_DATE_EPOCH,
) -> dict[str, Any]:
    """Build and inspect a wheel from the exact clean release archive."""

    source_archive = Path(archive_path).resolve()
    if not source_archive.is_file():
        raise ValueError(f"release archive does not exist: {source_archive}")
    _verify_sibling_checksum(source_archive)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="fta-release-wheel-") as directory:
        temporary_root = Path(directory)
        with zipfile.ZipFile(source_archive) as archive:
            names = archive.namelist()
            _validate_archive_paths(names)
            manifest_names = [
                name for name in names if name.endswith("/release-manifest.json")
            ]
            if len(manifest_names) != 1:
                raise ValueError(
                    "release archive must contain exactly one release-manifest.json"
                )
            embedded_manifest = json.loads(archive.read(manifest_names[0]))
            prefix = embedded_manifest.get("archive_prefix")
            if not isinstance(prefix, str) or not prefix.endswith("/"):
                raise ValueError("release manifest has an invalid archive_prefix")
            archive.extractall(temporary_root)

        source_root = temporary_root / prefix.removesuffix("/")
        if not source_root.is_dir():
            raise ValueError("release archive prefix directory is missing")
        required_setuptools = _required_setuptools_version(
            source_root / "pyproject.toml"
        )
        installed_setuptools = _installed_setuptools_version(python_executable)
        if installed_setuptools != required_setuptools:
            raise ValueError(
                f"wheel interpreter has setuptools {installed_setuptools!r}; "
                f"project requires exactly {required_setuptools!r}"
            )
        _normalize_tree_timestamps(source_root, source_date_epoch)
        wheel_output = temporary_root / "wheel-output"
        wheel_output.mkdir()
        environment = os.environ.copy()
        environment["SOURCE_DATE_EPOCH"] = str(source_date_epoch)
        completed = subprocess.run(
            [
                python_executable,
                "-m",
                "pip",
                "wheel",
                "--no-build-isolation",
                "--no-deps",
                "--wheel-dir",
                str(wheel_output),
                ".",
            ],
            cwd=source_root,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        if completed.returncode != 0:
            output = completed.stdout.strip()
            raise ValueError(f"clean wheel build failed:\n{output}")
        wheels = sorted(wheel_output.glob("*.whl"))
        if len(wheels) != 1:
            raise ValueError(
                f"clean wheel build produced {len(wheels)} wheel files, expected one"
            )
        expected_scripts = _project_script_count(source_root / "pyproject.toml")
        inspection = inspect_wheel(
            wheels[0],
            expected_console_scripts=expected_scripts,
        )
        wheel_path = destination / wheels[0].name
        shutil.copyfile(wheels[0], wheel_path)

    wheel_sha256 = sha256_file(wheel_path)
    checksum_path = wheel_path.with_suffix(wheel_path.suffix + ".sha256")
    checksum_path.write_text(
        f"{wheel_sha256}  {wheel_path.name}\n",
        encoding="utf-8",
    )
    report = {
        "schema_version": "1.0",
        "source_archive": str(source_archive),
        "source_archive_sha256": sha256_file(source_archive),
        "source_date_epoch": source_date_epoch,
        "wheel": str(wheel_path),
        "wheel_sha256": wheel_sha256,
        "wheel_size_bytes": wheel_path.stat().st_size,
        "setuptools_version": required_setuptools,
        "checksum_file": str(checksum_path),
        **inspection,
    }
    report_path = destination / (
        wheel_path.name.removesuffix(".whl") + "-wheel-report.json"
    )
    report_path.write_bytes(canonical_json(report))
    report["report"] = str(report_path)
    return report


def inspect_wheel(
    path: str | Path,
    *,
    expected_console_scripts: int | None = None,
) -> dict[str, Any]:
    """Reject local debris and verify installed console-entry-point metadata."""

    wheel_path = Path(path)
    with zipfile.ZipFile(wheel_path) as wheel:
        names = wheel.namelist()
        forbidden = [
            name
            for name in names
            if ".DS_Store" in PurePosixPath(name).parts
            or "__pycache__" in PurePosixPath(name).parts
            or name.endswith((".pyc", ".pyo"))
        ]
        if forbidden:
            raise ValueError(
                "wheel contains forbidden local artifacts: "
                + ", ".join(sorted(forbidden))
            )
        entrypoint_names = [
            name for name in names if name.endswith(".dist-info/entry_points.txt")
        ]
        if len(entrypoint_names) != 1:
            raise ValueError(
                "wheel must contain exactly one dist-info/entry_points.txt"
            )
        entrypoint_text = wheel.read(entrypoint_names[0]).decode("utf-8")
    console_scripts = _console_script_names(entrypoint_text)
    if (
        expected_console_scripts is not None
        and len(console_scripts) != expected_console_scripts
    ):
        raise ValueError(
            f"wheel has {len(console_scripts)} console scripts, "
            f"expected {expected_console_scripts}"
        )
    return {
        "wheel_file_count": len(names),
        "console_script_count": len(console_scripts),
        "console_scripts": console_scripts,
        "forbidden_artifact_count": 0,
    }


def _verify_sibling_checksum(archive_path: Path) -> None:
    checksum_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
    if not checksum_path.is_file():
        return
    fields = checksum_path.read_text(encoding="utf-8").strip().split()
    if not fields or fields[0] != sha256_file(archive_path):
        raise ValueError("release archive does not match its sibling checksum")


def _validate_archive_paths(names: Iterable[str]) -> None:
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe path in release archive: {name}")


def _normalize_tree_timestamps(root: Path, source_date_epoch: int) -> None:
    for path in sorted(root.rglob("*"), reverse=True):
        os.utime(path, (source_date_epoch, source_date_epoch), follow_symlinks=False)
    os.utime(root, (source_date_epoch, source_date_epoch), follow_symlinks=False)


def _project_script_count(path: Path) -> int:
    project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
    scripts = project.get("scripts", {})
    if not isinstance(scripts, dict):
        raise ValueError("project.scripts must be a table")
    return len(scripts)


def _required_setuptools_version(path: Path) -> str:
    value = tomllib.loads(path.read_text(encoding="utf-8"))
    requirements = value.get("build-system", {}).get("requires", [])
    if not isinstance(requirements, list):
        raise ValueError("build-system.requires must be an array")
    exact = [
        requirement.split("==", 1)[1]
        for requirement in requirements
        if isinstance(requirement, str) and requirement.startswith("setuptools==")
    ]
    if len(exact) != 1 or not exact[0]:
        raise ValueError("build-system must pin exactly one setuptools version")
    return exact[0]


def _installed_setuptools_version(python_executable: str) -> str:
    completed = subprocess.run(
        [
            python_executable,
            "-c",
            "import setuptools; print(setuptools.__version__)",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if completed.returncode != 0:
        raise ValueError(
            f"wheel interpreter cannot import setuptools:\n"
            f"{completed.stdout.strip()}"
        )
    return completed.stdout.strip()


def _console_script_names(entrypoint_text: str) -> list[str]:
    in_console_scripts = False
    names: list[str] = []
    for raw_line in entrypoint_text.splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            in_console_scripts = line == "[console_scripts]"
            continue
        if in_console_scripts and "=" in line:
            name, _ = line.split("=", 1)
            names.append(name.strip())
    return sorted(names)


def _zip_info(name: str, source_date_epoch: int) -> zipfile.ZipInfo:
    timestamp = datetime.fromtimestamp(source_date_epoch, timezone.utc)
    info = zipfile.ZipInfo(
        filename=name,
        date_time=(
            timestamp.year,
            timestamp.month,
            timestamp.day,
            timestamp.hour,
            timestamp.minute,
            timestamp.second,
        ),
    )
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def _read_text(path: Path, errors: list[str]) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        errors.append(f"unable to read {path.name}: {error}")
        return ""


def _read_json_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"invalid {path.name}: {error}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path.name} must contain a JSON object")
        return {}
    return value


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _cff_scalar(text: str, key: str) -> str | None:
    match = re.search(
        rf"(?m)^\s*(?:-\s*)?{re.escape(key)}:\s*(?P<value>.+?)\s*$",
        text,
    )
    if match is None:
        return None
    return match.group("value").strip().strip("\"'")


def _cff_author(text: str) -> str | None:
    family = _cff_scalar(text, "family-names")
    given = _cff_scalar(text, "given-names")
    if family is None or given is None:
        return None
    return f"{given} {family}"


def _zenodo_author(zenodo: dict[str, Any]) -> str | None:
    creators = zenodo.get("creators")
    if not isinstance(creators, list) or not creators:
        return None
    first = creators[0]
    if not isinstance(first, dict):
        return None
    name = first.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    if "," in name:
        family, given = (part.strip() for part in name.split(",", 1))
        return f"{given} {family}"
    return name.strip()


def _package_version(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r'(?m)^__version__\s*=\s*"([^"]+)"\s*$', text)
    return match.group(1) if match else None


def _source_date_epoch(value: str | None) -> int:
    if value is None:
        return DEFAULT_SOURCE_DATE_EPOCH
    try:
        return int(value)
    except ValueError as error:
        raise ValueError("SOURCE_DATE_EPOCH must be an integer") from error


def main(argv: list[str] | None = None) -> int:
    """Run a release audit or build a deterministic candidate archive."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path("dist"))
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument(
        "--wheel-from-archive",
        type=Path,
        help="build a clean, inspected wheel from this release ZIP",
    )
    parser.add_argument(
        "--wheel-python",
        default=sys.executable,
        help="Python interpreter whose installed build backend creates the wheel",
    )
    parser.add_argument("--require-publication-ready", action="store_true")
    parser.add_argument(
        "--source-date-epoch",
        type=int,
        default=None,
        help="normalized ZIP timestamp; defaults to SOURCE_DATE_EPOCH or 1980-01-01",
    )
    args = parser.parse_args(argv)
    try:
        if args.audit_only and args.wheel_from_archive is not None:
            parser.error("--audit-only and --wheel-from-archive are mutually exclusive")
        if args.audit_only:
            report = audit_release(args.root)
        elif args.wheel_from_archive is not None:
            source_date_epoch = (
                args.source_date_epoch
                if args.source_date_epoch is not None
                else _source_date_epoch(os.environ.get("SOURCE_DATE_EPOCH"))
            )
            report = build_wheel_from_release_archive(
                archive_path=args.wheel_from_archive,
                output_dir=args.output_dir,
                python_executable=args.wheel_python,
                source_date_epoch=source_date_epoch,
            )
        else:
            source_date_epoch = (
                args.source_date_epoch
                if args.source_date_epoch is not None
                else _source_date_epoch(os.environ.get("SOURCE_DATE_EPOCH"))
            )
            report = build_release_bundle(
                root=args.root,
                output_dir=args.output_dir,
                require_publication_ready=args.require_publication_ready,
                source_date_epoch=source_date_epoch,
            )
    except ValueError as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.audit_only and report["errors"]:
        return 2
    if args.require_publication_ready and not report["publication_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
