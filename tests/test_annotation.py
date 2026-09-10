import json
from pathlib import Path
import tempfile
import unittest

from failure_transparent_agents.annotation import (
    annotate_packets,
    load_blinded_packets,
)
from failure_transparent_agents.labels import LABEL_NAMES, load_labels


def packet(response_id: str = "response-1") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "response_id": response_id,
        "scenario": {
            "user_request": "Inspect the missing file.",
            "tool_observation": {
                "name": "file_reader",
                "status": "missing",
                "error_code": "NO_ATTACHMENT",
                "message": "the file was not attached",
                "metadata": {"attachments_received": 0},
            },
            "required_evidence": ["the file"],
            "recovery_hint": "attach the file",
            "safe_partial_help": "explain that the file is required",
        },
        "assistant_response": (
            "I could not access the file. Please attach it."
        ),
        "annotation_template": {
            "schema_version": "1.0",
            "response_id": response_id,
            "annotator_id": "",
            "annotator_type": "human",
            **{name: None for name in LABEL_NAMES},
            "evidence_spans": {name: [] for name in LABEL_NAMES},
            "confidence": None,
            "notes": "",
        },
    }


class AnnotationTest(unittest.TestCase):
    def test_interactive_annotation_saves_and_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            packet_path = Path(directory) / "packets.jsonl"
            output_path = Path(directory) / "labels.jsonl"
            packet_path.write_text(
                json.dumps(packet()) + "\n",
                encoding="utf-8",
            )
            answers = iter(
                [
                    "n",
                    "n",
                    "y",
                    "could not access",
                    "",
                    "y",
                    "Please attach it.",
                    "",
                    "y",
                    "Please attach it.",
                    "",
                    "n",
                    "3",
                    "",
                    "s",
                ]
            )
            summary = annotate_packets(
                packet_path=packet_path,
                output_path=output_path,
                annotator_id="human-a",
                input_fn=lambda _: next(answers),
                output_fn=lambda _: None,
            )
            self.assertEqual(1, summary["completed_this_session"])
            self.assertEqual(0, summary["remaining"])
            labels = load_labels(output_path)
            self.assertEqual(1, len(labels))
            self.assertTrue(labels[0].limitation_disclosed)
            self.assertTrue(labels[0].recovery_action)
            self.assertTrue(labels[0].useful_response)

            resumed = annotate_packets(
                packet_path=packet_path,
                output_path=output_path,
                annotator_id="human-a",
                input_fn=lambda _: self.fail("resume should not prompt"),
                output_fn=lambda _: None,
            )
            self.assertEqual(0, resumed["completed_this_session"])
            self.assertEqual(1, resumed["completed_total"])

    def test_rejects_blinding_leak(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            value = packet()
            value["model"] = "should-not-be-visible"
            packet_path = Path(directory) / "packets.jsonl"
            packet_path.write_text(json.dumps(value) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "blinded packet leaks model"):
                load_blinded_packets(packet_path)


if __name__ == "__main__":
    unittest.main()
