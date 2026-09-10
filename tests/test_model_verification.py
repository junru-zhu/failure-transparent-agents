import json
from pathlib import Path
import tempfile
import unittest

from failure_transparent_agents.model_verification import (
    validate_model_verification,
)


ROOT = Path(__file__).parents[1]


class ModelVerificationTest(unittest.TestCase):
    def test_repository_snapshot_matches_every_config(self) -> None:
        summary = validate_model_verification(
            ROOT / "data" / "model_verification.json",
            provider_config_paths=sorted(
                (ROOT / "configs" / "providers").glob("*.json")
            ),
            judge_config_paths=sorted(
                (ROOT / "configs" / "judges").glob("*.json")
            ),
        )
        self.assertTrue(summary["ready"])
        self.assertEqual(4, summary["arm_count"])
        self.assertEqual("verified", summary["status"])

    def test_rejects_stale_config_hash(self) -> None:
        snapshot = json.loads(
            (ROOT / "data" / "model_verification.json").read_text(
                encoding="utf-8"
            )
        )
        snapshot["arms"][0]["config_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "verification.json"
            path.write_text(json.dumps(snapshot), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "config hash is stale"):
                validate_model_verification(
                    path,
                    provider_config_paths=sorted(
                        (ROOT / "configs" / "providers").glob("*.json")
                    ),
                    judge_config_paths=sorted(
                        (ROOT / "configs" / "judges").glob("*.json")
                    ),
                )


if __name__ == "__main__":
    unittest.main()
