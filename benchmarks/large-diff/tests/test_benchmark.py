import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "benchmark", Path(__file__).resolve().parents[1] / "run.py"
)
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


class FixtureTest(unittest.TestCase):
    def test_size_variants_are_isolated_and_keep_the_code_change(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "source"
            repository.mkdir()
            benchmark.git(repository, "init")
            benchmark.git(repository, "config", "user.name", "Fixture Test")
            benchmark.git(repository, "config", "user.email", "fixture@example.invalid")
            (repository / "app.py").write_text("value = 1\n")
            benchmark.git(repository, "add", ".")
            benchmark.git(repository, "commit", "-m", "base")
            base = benchmark.git(repository, "rev-parse", "HEAD").decode().strip()
            (repository / "app.py").write_text("value = 2\n")
            (repository / "model.json").write_text('{"generated": true}\n')
            (repository / "link.py").symlink_to("app.py")
            benchmark.git(repository, "add", ".")
            benchmark.git(repository, "commit", "-m", "head")
            head = benchmark.git(repository, "rev-parse", "HEAD").decode().strip()
            fixture = {
                "repository": "public/example", "pull_request": 1,
                "base_sha": base, "head_sha": head, "title": "Fixture", "body": "",
                "variants": {"full": [], "reduced": ["model.json"]},
            }
            full = benchmark.prepare(repository, fixture, "full", root / "full")
            reduced = benchmark.prepare(repository, fixture, "reduced", root / "reduced")
            self.assertGreater(full["diff_bytes"], reduced["diff_bytes"])
            self.assertTrue((root / "full/head/model.json").exists())
            self.assertFalse((root / "reduced/head/model.json").exists())
            self.assertFalse((root / "full/head/link.py").exists())
            self.assertFalse((root / "full/head/.git").exists())
            for variant in ("full", "reduced"):
                self.assertEqual((root / variant / "base/app.py").read_text(), "value = 1\n")
                self.assertEqual((root / variant / "head/app.py").read_text(), "value = 2\n")
                self.assertIn("+value = 2", (root / variant / "context/diff.patch").read_text())
            (root / "full/head/app.py").write_text("redacted\n")
            benchmark.prepare(repository, fixture, "full", root / "repeat")
            self.assertEqual((root / "repeat/head/app.py").read_text(), "value = 2\n")
            with self.assertRaisesRegex(ValueError, "fresh"):
                benchmark.prepare(repository, fixture, "full", root / "repeat")

    def test_fixture_paths_cannot_escape_snapshots(self):
        fixture = json.loads((Path(__file__).resolve().parents[1] / "fixture.json").read_text())
        fixture["variants"]["reduced"] = ["../outside"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.json"
            path.write_text(json.dumps(fixture))
            with self.assertRaisesRegex(ValueError, "inside"):
                benchmark.load_fixture(path)


class ResultTest(unittest.TestCase):
    def test_timeout_keeps_partial_usage_without_claiming_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            events = [
                {"event": "run_start", "prompt_sha256": "prompt", "policy_sha256": "policy"},
                {"event": "context", "sha256": "context", "bytes": 1234},
                {"event": "tool_request", "tool": "Read"},
                {"event": "tool_request", "tool": "Grep"},
                {"event": "wall_clock_timeout", "api_messages": 2, "seconds": 2870},
                {"event": "run_failed", "reason": "wall-clock timeout"},
            ]
            (output / "transcript.jsonl").write_text(
                "\n".join(json.dumps(event) for event in events)
            )
            result = benchmark.summarize(output, 1, 2871)
            self.assertFalse(result["accepted"])
            self.assertTrue(result["timed_out"])
            self.assertEqual(result["tool_calls"], 2)
            self.assertEqual(result["api_messages"], 2)
            self.assertEqual(result["submission_calls"], 0)
            self.assertEqual(result["failure_reason"], "wall-clock timeout")

    def test_acceptance_requires_success_and_an_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            self.assertFalse(benchmark.summarize(output, 0, 1)["accepted"])
            (output / "review.json").write_text("{}")
            self.assertFalse(benchmark.summarize(output, 1, 1)["accepted"])
            self.assertTrue(benchmark.summarize(output, 0, 1)["accepted"])


if __name__ == "__main__":
    unittest.main()
