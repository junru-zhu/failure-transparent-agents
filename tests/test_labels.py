import json
from pathlib import Path
import tempfile
import unittest

from failure_transparent_agents.labels import LABEL_NAMES, ResponseLabel, load_labels


def label_value() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "response_id": "run:model:scenario:condition:0",
        "annotator_id": "human-01",
        "annotator_type": "human",
        "false_success": False,
        "fabricated_details": False,
        "limitation_disclosed": True,
        "recovery_action": True,
        "useful_response": True,
        "over_refusal": False,
        "evidence_spans": {
            name: (["could not access"] if name == "limitation_disclosed" else [])
            for name in LABEL_NAMES
        },
        "confidence": 3,
        "notes": "",
    }


class ResponseLabelTest(unittest.TestCase):
    def test_parses_and_round_trips_label(self) -> None:
        label = ResponseLabel.from_dict(label_value())
        self.assertTrue(label.limitation_disclosed)
        self.assertEqual("human", label.annotator_type)
        self.assertEqual(label_value(), label.to_dict())

    def test_rejects_missing_evidence_label(self) -> None:
        value = label_value()
        del value["evidence_spans"]["over_refusal"]  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "every label"):
            ResponseLabel.from_dict(value)

    def test_rejects_duplicate_annotator_response_pair(self) -> None:
        encoded = json.dumps(label_value())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "labels.jsonl"
            path.write_text(f"{encoded}\n{encoded}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate label"):
                load_labels(path)


if __name__ == "__main__":
    unittest.main()
