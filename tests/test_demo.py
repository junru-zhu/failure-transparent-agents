import io
import unittest
from contextlib import redirect_stdout

from failure_transparent_agents.demo import main, render_demo


class DemoTest(unittest.TestCase):
    def test_demo_exercises_failure_and_transparency_paths(self) -> None:
        output = render_demo()

        self.assertIn("NO_ATTACHMENT", output)
        self.assertIn("[baseline] UNSUPPORTED SUCCESS", output)
        self.assertIn("[transparency] FAILURE TRANSPARENT", output)
        self.assertIn("[evidence_contract] FAILURE TRANSPARENT", output)
        self.assertIn("baseline 32.0%", output)
        self.assertIn("not human-validated", output)

    def test_main_prints_demo(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            status = main([])

        self.assertEqual(status, 0)
        self.assertIn("60-second offline tour", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
