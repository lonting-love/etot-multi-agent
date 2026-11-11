import tempfile
import unittest
from pathlib import Path

from modules import memory
from modules.config import MAX_ROUNDS
from modules.graph_builder import _dedupe_sources, route_after_critic


class RoutingTests(unittest.TestCase):
    def test_passed_goes_done(self):
        state = {"critic_result": {"passed": True}, "round": 1}
        self.assertEqual(route_after_critic(state), "done")

    def test_failed_rewrites(self):
        state = {"critic_result": {"passed": False}, "round": 1}
        self.assertEqual(route_after_critic(state), "rewrite")

    def test_max_rounds_forces_done(self):
        state = {"critic_result": {"passed": False}, "round": MAX_ROUNDS}
        self.assertEqual(route_after_critic(state), "done")

    def test_source_failure_skips_rewrite(self):
        state = {"critic_result": {"passed": False}, "round": 1, "sources_failed": True}
        self.assertEqual(route_after_critic(state), "done")


class SourceDedupeTests(unittest.TestCase):
    def test_duplicate_url_lines_removed(self):
        text = "1. A\n   链接: https://a.com/1\n2. A again\n   链接: https://a.com/1\n3. B\n   链接: https://b.com/2"
        deduped = _dedupe_sources(text)
        self.assertEqual(deduped.count("https://a.com/1"), 1)
        self.assertIn("https://b.com/2", deduped)


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original = memory.DB_PATH
        memory.DB_PATH = str(Path(self.tmp.name) / "memory.db")
        memory.init()

    def tearDown(self):
        memory.DB_PATH = self.original
        self.tmp.cleanup()

    def test_append_and_load_in_order(self):
        memory.append_message("s1", "user", "问题1")
        memory.append_message("s1", "assistant", "回答1")
        history = memory.load_history("s1")
        self.assertEqual([item["role"] for item in history], ["user", "assistant"])
        self.assertEqual(history[0]["content"], "问题1")

    def test_sessions_isolated(self):
        memory.append_message("s1", "user", "A")
        memory.append_message("s2", "user", "B")
        self.assertEqual(len(memory.load_history("s2")), 1)
        self.assertEqual(memory.load_history("s2")[0]["content"], "B")


if __name__ == "__main__":
    unittest.main()
