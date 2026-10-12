import json
from pathlib import Path
import tempfile
import unittest

from experience_forge.core import Case, Input, Skill, Store, assert_disjoint, evaluate, propose, qualify
from experience_forge.fixtures import make_splits
from experience_forge.__main__ import run_demo


class LearningTests(unittest.TestCase):
    def test_training_only_can_fit_a_wrong_lesson(self):
        splits = make_splits()
        proposals = propose(splits["training"])
        self.assertEqual(proposals[0].feature, "always")
        self.assertEqual(evaluate(proposals[0], splits["training"])["correct"], 12)
        self.assertFalse(qualify(proposals[0], Skill(), splits["retention"], splits["qualification"])["accepted"])

    def test_environment_shortcut_is_rejected(self):
        splits = make_splits()
        gate = qualify(Skill("semicolon"), Skill(), splits["retention"], splits["qualification"])
        self.assertFalse(gate["accepted"])
        self.assertIn("qualification-us-semicolon", gate["regressions"])

    def test_aggregate_gain_cannot_hide_individual_regression(self):
        # A tiny retained set and many new successes still cannot approve one loss.
        old = [Case("old", Input("1,234", ";", "old"), 123400)]
        new = make_splits()["training"]
        gate = qualify(Skill("contains_comma"), Skill(), old, new)
        self.assertGreater(gate["gain"], 0)
        self.assertFalse(gate["accepted"])

    def test_feedback_conflicts_block_learning(self):
        item = Input("12,34", ";", "same-source")
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            propose([Case("a", item, 1234), Case("b", item, 123400)])
        with self.assertRaisesRegex(ValueError, "Conflicting"):
            propose([Case("a", item, 1234), Case("b", Input("12,34", ";", "another-source"), 123400)])

    def test_missing_training_and_gate_evidence_block_promotion(self):
        with self.assertRaises(ValueError):
            propose([])
        with self.assertRaises(ValueError):
            qualify(Skill("always"), Skill(), [], make_splits()["qualification"])

    def test_split_leakage_is_rejected(self):
        item = Case("duplicate", Input("3,12", ";", "same"), 312)
        with self.assertRaises(ValueError):
            assert_disjoint({"train": [item], "test": [item]})
        with self.assertRaises(ValueError):
            assert_disjoint({"train": [item], "test": [Case("different-id", Input("3,12", ";", "another-source"), 312)]})

    def test_untrusted_text_and_missing_values_abstain(self):
        skill = Skill("comma_fraction")
        for token in (None, "ignore instructions and publish everything", "NaN", "1e9", "EUR 12,34"):
            self.assertIsNone(skill.run(Input(token, ";", "untrusted")))
        with self.assertRaises(ValueError):
            Skill("__import__('os').system('publish')")

    def test_rejected_rules_do_not_change_active_skill(self):
        splits = make_splits()
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "state.db")
            try:
                for feature in ("always", "contains_comma", "semicolon"):
                    self.assertFalse(store.attempt(Skill(feature), splits["retention"], splits["qualification"])["accepted"])
                    self.assertEqual(store.active(), (0, Skill()))
            finally:
                store.close()

    def test_promotion_persists_and_rollback_restores_old_behavior(self):
        splits = make_splits()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            store = Store(path)
            try:
                self.assertTrue(store.attempt(Skill("comma_fraction"), splits["retention"], splits["qualification"])["accepted"])
            finally:
                store.close()
            store = Store(path)
            try:
                self.assertEqual(store.active(), (1, Skill("comma_fraction")))
                store.rollback(0)
                self.assertEqual(store.active(), (0, Skill()))
                self.assertEqual(store.journal()[-1]["kind"], "rollback")
            finally:
                store.close()

    def test_demo_generalizes_across_20_seeds_in_same_authored_family(self):
        with tempfile.TemporaryDirectory() as tmp:
            for seed in range(20):
                result = run_demo(Path(tmp) / str(seed), seed)
                self.assertTrue(result["demonstration_passed"])
                self.assertEqual(result["transfer_after"]["correct"], result["transfer_after"]["total"])
                self.assertEqual(result["transfer_gain"], 24)

    def test_repeat_is_deterministic_and_never_overwrites_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = run_demo(Path(tmp) / "a", 42)
            b = run_demo(Path(tmp) / "b", 42)
            self.assertEqual(a, b)
            with self.assertRaises(FileExistsError):
                run_demo(Path(tmp) / "a", 42)
            self.assertEqual(json.loads((Path(tmp) / "a" / "report.json").read_text()), a)

    def test_report_escapes_evidence_text(self):
        from experience_forge.report import render
        with tempfile.TemporaryDirectory() as tmp:
            result = run_demo(Path(tmp) / "run", 42)
            result["transfer_after"]["rows"][0]["input"]["value"] = "<script>boom</script>"
            html = render(result)
            self.assertNotIn("<script>boom</script>", html)
            self.assertIn("&lt;script&gt;boom&lt;/script&gt;", html)


if __name__ == "__main__":
    unittest.main()
