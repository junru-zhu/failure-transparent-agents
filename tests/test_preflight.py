import json
from pathlib import Path
import unittest

from failure_transparent_agents.preflight import (
    SOURCE_DRIFT_BLOCKER,
    build_preflight_plan,
    completed_run_validation,
)


ROOT = Path(__file__).parents[1]


class ConfirmatoryPreflightTest(unittest.TestCase):
    def test_validates_full_matrix_without_credentials(self) -> None:
        plan = build_preflight_plan(
            dataset_path=ROOT / "data" / "confirmatory_scenarios.jsonl",
            dataset_manifest_path=ROOT / "data" / "confirmatory_manifest.json",
            provider_config_paths=sorted(
                (ROOT / "configs" / "providers").glob("*.json")
            ),
            judge_config_paths=sorted(
                (ROOT / "configs" / "judges").glob("*.json")
            ),
            approval_path=ROOT / "data" / "confirmatory_approval.json",
            model_verification_path=ROOT / "data" / "model_verification.json",
            repeats=2,
        )

        self.assertTrue(plan["offline_only"])
        self.assertEqual(0, plan["network_calls_made"])
        self.assertEqual(100, plan["base_task_count"])
        self.assertEqual(100, plan["task_instance_count"])
        self.assertEqual(1800, plan["planned_primary_responses"])
        self.assertEqual(3600, plan["maximum_provider_attempts"])
        self.assertEqual(3, len(plan["arms"]))
        self.assertEqual(1, len(plan["judge_arms"]))
        self.assertTrue(all(arm["max_calls_ok"] for arm in plan["arms"]))
        self.assertTrue(all(arm["budget_ok"] for arm in plan["arms"]))
        self.assertTrue(plan["judge_arms"][0]["max_calls_ok"])
        self.assertTrue(plan["judge_arms"][0]["budget_ok"])
        self.assertEqual(120.0, plan["aggregate_budget_cap_usd"])
        self.assertGreater(plan["judge_preflight_max_cost_usd"], 40)
        manifest = json.loads(
            (ROOT / "data" / "confirmatory_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        if manifest["frozen"]:
            self.assertNotIn(
                "dataset requires author freeze",
                plan["blocking_checks"],
            )
        else:
            self.assertIn(
                "dataset requires author freeze",
                plan["blocking_checks"],
            )
        self.assertNotIn(
            "collection approval requires explicit authorization",
            plan["blocking_checks"],
        )
        self.assertEqual("approved", plan["collection_approval"]["status"])
        self.assertTrue(plan["collection_approval"]["ready"])
        self.assertTrue(plan["model_verification"]["ready"])
        self.assertEqual(4, plan["model_verification"]["arm_count"])
        self.assertEqual(
            not plan["blocking_checks"],
            plan["ready_for_live_run"],
        )

    def test_completed_run_validation_never_authorizes_collection(self) -> None:
        plan = {
            "dataset_frozen": True,
            "collection_approval": {"ready": True},
            "model_verification": {"ready": True},
            "frozen_source_hashes_ok": False,
            "blocking_checks": [SOURCE_DRIFT_BLOCKER],
        }

        validation = completed_run_validation(plan)

        self.assertTrue(validation["passed"])
        self.assertFalse(validation["live_run_authorized"])
        self.assertTrue(validation["accepted_post_freeze_source_drift"])
        self.assertEqual([], validation["unexpected_blocking_checks"])

    def test_completed_run_validation_rejects_other_blockers(self) -> None:
        plan = {
            "dataset_frozen": True,
            "collection_approval": {"ready": True},
            "model_verification": {"ready": True},
            "frozen_source_hashes_ok": False,
            "blocking_checks": [
                SOURCE_DRIFT_BLOCKER,
                "openai/model: frozen config hash",
            ],
        }

        validation = completed_run_validation(plan)

        self.assertFalse(validation["passed"])
        self.assertFalse(validation["live_run_authorized"])
        self.assertEqual(
            ["openai/model: frozen config hash"],
            validation["unexpected_blocking_checks"],
        )


if __name__ == "__main__":
    unittest.main()
