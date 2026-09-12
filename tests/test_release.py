import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

from failure_transparent_agents.release import (
    _resolve_executable,
    audit_release,
    build_release_bundle,
    inspect_wheel,
)


ROOT = Path(__file__).parents[1]


class ReleaseTest(unittest.TestCase):
    def test_resolves_relative_wheel_interpreter_before_chdir(self) -> None:
        relative = Path(".venv") / "bin" / "python"
        if relative.is_file():
            self.assertEqual(
                str(relative.absolute()),
                _resolve_executable(str(relative)),
            )

    def test_repository_is_locally_release_ready(self) -> None:
        audit = audit_release(ROOT)
        self.assertEqual([], audit["errors"])
        self.assertTrue(audit["local_release_ready"])
        self.assertEqual(100, audit["dataset_rows"])
        self.assertNotIn(
            "collection approval is not approved",
            audit["publication_blockers"],
        )
        self.assertNotIn(
            "public repository URL has not been selected",
            audit["publication_blockers"],
        )
        manifest = json.loads(
            (ROOT / "data" / "confirmatory_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        signoff_blocker = "confirmatory manifest has no author signoff"
        if manifest["frozen"]:
            self.assertNotIn(signoff_blocker, audit["publication_blockers"])
        else:
            self.assertIn(signoff_blocker, audit["publication_blockers"])
        self.assertEqual(
            bool(manifest["frozen"]),
            audit["publication_ready"],
        )

    def test_bundle_is_deterministic_and_excludes_local_artifacts(self) -> None:
        with (
            tempfile.TemporaryDirectory() as first_directory,
            tempfile.TemporaryDirectory() as second_directory,
        ):
            repository_audit = audit_release(ROOT)
            first = build_release_bundle(
                root=ROOT,
                output_dir=first_directory,
            )
            second = build_release_bundle(
                root=ROOT,
                output_dir=second_directory,
            )
            self.assertEqual(first["archive_sha256"], second["archive_sha256"])
            self.assertEqual(
                repository_audit["publication_ready"],
                first["publication_ready"],
            )

            with zipfile.ZipFile(first["archive"]) as archive:
                names = archive.namelist()
                prefix = (
                    "failure-transparent-agents-"
                    f"{repository_audit['version']}/"
                )
                self.assertIn(prefix + "release-manifest.json", names)
                self.assertIn(prefix + "data/confirmatory_scenarios.jsonl", names)
                self.assertIn(prefix + "paper/main.pdf", names)
                self.assertFalse(any("/results/" in name for name in names))
                self.assertFalse(any("__pycache__" in name for name in names))
                self.assertFalse(any(name.endswith(".DS_Store") for name in names))
                manifest = json.loads(
                    archive.read(prefix + "release-manifest.json")
                )
                self.assertEqual(100, manifest["dataset_rows"])
                self.assertTrue(manifest["local_release_ready"])

    def test_audit_detects_metadata_drift_and_secret_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "repository"
            shutil.copytree(
                ROOT,
                copied,
                ignore=shutil.ignore_patterns(
                    ".DS_Store",
                    "__pycache__",
                    "*.egg-info",
                    "build",
                    "dist",
                    "results",
                ),
            )
            zenodo = json.loads(
                (copied / ".zenodo.json").read_text(encoding="utf-8")
            )
            zenodo["version"] = "9.9.9"
            (copied / ".zenodo.json").write_text(
                json.dumps(zenodo),
                encoding="utf-8",
            )
            (copied / "docs" / "leak.txt").write_text(
                "sk-" + ("a" * 24),
                encoding="utf-8",
            )

            audit = audit_release(copied)
            self.assertFalse(audit["local_release_ready"])
            self.assertTrue(
                any(".zenodo.json version" in error for error in audit["errors"])
            )
            self.assertTrue(
                any("OpenAI-style secret key" in error for error in audit["errors"])
            )

    def test_wheel_inspection_rejects_local_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            wheel_path = Path(directory) / "bad.whl"
            with zipfile.ZipFile(wheel_path, "w") as wheel:
                wheel.writestr(".DS_Store", b"local metadata")
                wheel.writestr(
                    "example-0.0.0.dist-info/entry_points.txt",
                    "[console_scripts]\nexample = example:main\n",
                )
            with self.assertRaisesRegex(ValueError, "forbidden local artifacts"):
                inspect_wheel(wheel_path, expected_console_scripts=1)

    def test_wheel_inspection_counts_console_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            wheel_path = Path(directory) / "good.whl"
            with zipfile.ZipFile(wheel_path, "w") as wheel:
                wheel.writestr("example/__init__.py", b"")
                wheel.writestr(
                    "example-0.0.0.dist-info/entry_points.txt",
                    (
                        "[console_scripts]\n"
                        "example-a = example:a\n"
                        "example-b = example:b\n"
                    ),
                )
            inspection = inspect_wheel(
                wheel_path,
                expected_console_scripts=2,
            )
            self.assertEqual(2, inspection["console_script_count"])
            self.assertEqual(
                ["example-a", "example-b"],
                inspection["console_scripts"],
            )


if __name__ == "__main__":
    unittest.main()
