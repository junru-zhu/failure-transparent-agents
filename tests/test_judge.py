import json
import unittest

from failure_transparent_agents.judge import parse_judge_label
from failure_transparent_agents.labels import LABEL_NAMES


class JudgeParsingTest(unittest.TestCase):
    def test_attaches_metadata_and_validates_verbatim_spans(self) -> None:
        response = "I could not access the file. Please upload it."
        values = {
            "false_success": False,
            "fabricated_details": False,
            "limitation_disclosed": True,
            "recovery_action": True,
            "useful_response": True,
            "over_refusal": False,
        }
        payload = {
            **values,
            "evidence_spans": {
                name: (
                    ["I could not access the file."]
                    if name == "limitation_disclosed"
                    else ["Please upload it."]
                    if name in {"recovery_action", "useful_response"}
                    else []
                )
                for name in LABEL_NAMES
            },
            "confidence": 3,
            "notes": "",
        }
        label = parse_judge_label(
            json.dumps(payload),
            response_id="resp-1",
            annotator_id="judge-1",
            assistant_response=response,
        )
        self.assertEqual("resp-1", label.response_id)
        self.assertEqual("judge-1", label.annotator_id)
        self.assertTrue(label.limitation_disclosed)

    def test_rejects_nonverbatim_span(self) -> None:
        payload = {
            **{name: False for name in LABEL_NAMES},
            "limitation_disclosed": True,
            "evidence_spans": {
                **{name: [] for name in LABEL_NAMES},
                "limitation_disclosed": ["Not an exact quote."],
            },
            "confidence": 2,
            "notes": "",
        }
        with self.assertRaisesRegex(ValueError, "not verbatim"):
            parse_judge_label(
                json.dumps(payload),
                response_id="resp-1",
                annotator_id="judge-1",
                assistant_response="I could not access the file.",
            )


if __name__ == "__main__":
    unittest.main()
