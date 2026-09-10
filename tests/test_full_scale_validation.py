from pathlib import Path
import tempfile
import unittest

from failure_transparent_agents.full_scale_validation import (
    run_full_scale_validation,
)


ROOT = Path(__file__).parents[1]


class FullScaleValidationTest(unittest.TestCase):
    def test_exercises_all_1800_response_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = run_full_scale_validation(
                dataset_path=ROOT / "data" / "confirmatory_scenarios.jsonl",
                output_dir=directory,
                bootstrap_repetitions=10,
                permutation_repetitions=20,
            )
            self.assertTrue(manifest["scientific_use_prohibited"])
            self.assertEqual(1800, manifest["responses"])
            self.assertEqual(1800, manifest["model_labels"])
            self.assertEqual(540, manifest["human_initial_labels"])
            self.assertGreater(manifest["human_disagreement_responses"], 0)
            self.assertEqual(
                manifest["human_disagreement_responses"],
                manifest["human_adjudicated_labels"],
            )
            self.assertEqual(270, manifest["human_labels"])
            self.assertTrue(
                (
                    Path(directory)
                    / "human"
                    / "adjudication"
                    / "human_human_agreement.json"
                ).is_file()
            )
            self.assertTrue(
                (Path(directory) / "analysis" / "analysis_summary.json").is_file()
            )
            self.assertTrue(
                (
                    Path(directory)
                    / "analysis"
                    / "figures"
                    / "figure1_false_success_by_model.svg"
                ).is_file()
            )


if __name__ == "__main__":
    unittest.main()
