from pathlib import Path
import subprocess
import tempfile
import unittest

from failure_transparent_agents.final_release import (
    _require_clean_git_snapshot,
    _scan_bytes,
)


class FinalReleaseTest(unittest.TestCase):
    def test_requires_clean_fully_tracked_git_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(
                ["git", "init", "-q", str(root)],
                check=True,
            )
            (root / "tracked.txt").write_text("release input\n")
            subprocess.run(
                ["git", "-C", str(root), "add", "tracked.txt"],
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "-c",
                    "user.name=Test Author",
                    "-c",
                    "user.email=test@example.invalid",
                    "commit",
                    "-q",
                    "-m",
                    "fixture",
                ],
                check=True,
            )
            _require_clean_git_snapshot(root)

            (root / "untracked.txt").write_text("not committed\n")
            with self.assertRaisesRegex(
                ValueError,
                "clean, fully tracked",
            ):
                _require_clean_git_snapshot(root)

    def test_strict_scan_rejects_local_user_path(self) -> None:
        private_path = b"/" + b"Users" + b"/person/private/file"
        with self.assertRaisesRegex(ValueError, "macOS user path"):
            _scan_bytes("fixture.txt", private_path)


if __name__ == "__main__":
    unittest.main()
