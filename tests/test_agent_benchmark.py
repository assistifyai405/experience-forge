from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from experience_forge.connector_tasks import AffineRule, ConnectorWorld, make_connector_splits, qualify_rule, assert_connector_disjoint
from experience_forge.local_agent import LocalModel, run_agent
from experience_forge.agent_benchmark import MemoryBank, CapturedModel, VARIANTS


class ScriptedTestModel:
    """Tool-loop contract test control, never used in live benchmark results."""
    def __init__(self, messages):
        self.messages = iter(messages)
        self.calls = 0
        self.tokens = {"input": 0, "output": 0}

    def chat(self, *args, **kwargs):
        self.calls += 1
        return {"done": True, "done_reason": "stop", "message": next(self.messages)}


def tool(name, **arguments):
    return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": arguments}}]}


class AgentBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.splits = make_connector_splits(31415)
        self.case = self.splits["training"][0]
        a, b = self.case.examples
        self.scale = (b[0] - a[0]) // (b[1] - a[1])
        self.offset = a[0] - self.scale * a[1]
        self.rule = AffineRule(self.case.source, self.case.revision, self.scale, self.offset)

    def test_completion_prose_cannot_substitute_for_actual_saved_state(self):
        model = ScriptedTestModel([{"role": "assistant", "content": "Saved and verified successfully."}])
        result = run_agent(model, self.case, [], 1, "test")
        self.assertFalse(result["grade"]["passed"])
        self.assertIsNone(result["grade"]["actual"])

    def test_correct_write_without_verification_is_not_a_success(self):
        model = ScriptedTestModel([tool("save_quantity", quantity=self.case.expected), {"role": "assistant", "content": "Done."}])
        self.assertFalse(run_agent(model, self.case, [], 1, "test")["grade"]["passed"])

    def test_real_tool_loop_requires_correct_single_write_and_readback(self):
        model = ScriptedTestModel([tool("normalize_quantity", scale=self.scale, offset=self.offset),
            tool("save_quantity", quantity=self.case.expected), tool("read_saved_quantity"),
            {"role": "assistant", "content": "Saved and verified."}])
        result = run_agent(model, self.case, [self.rule], 1, "test")
        self.assertTrue(result["grade"]["passed"])
        self.assertEqual(result["model_calls"], 4)

    def test_repeated_write_fails_even_when_final_value_is_correct(self):
        model = ScriptedTestModel([tool("save_quantity", quantity=self.case.expected), tool("save_quantity", quantity=self.case.expected),
            tool("read_saved_quantity"), {"role": "assistant", "content": "Done."}])
        self.assertFalse(run_agent(model, self.case, [], 1, "test")["grade"]["passed"])

    def test_missing_input_abstains_without_a_write(self):
        case = next(case for case in self.splits["transfer"] if case.raw is None)
        model = ScriptedTestModel([{"role": "assistant", "content": "Missing input; nothing saved."}])
        self.assertTrue(run_agent(model, case, [], 1, "test")["grade"]["passed"])

    def test_unknown_tools_and_injection_cannot_execute_code(self):
        world = ConnectorWorld(self.case)
        try:
            self.assertIn("error", world.execute("publish_everything", {}))
            self.assertIn("error", world.execute("save_quantity", {"quantity": "__import__('os')"}))
            self.assertIsNone(world.grade(True)["actual"])
        finally:
            world.close()

    def test_rule_gate_rejects_wrong_coefficients_and_preserves_current_rule(self):
        wrong = replace(self.rule, offset=self.offset + 1)
        self.assertFalse(qualify_rule(wrong, self.splits["qualification"], [(self.rule, self.case)])["accepted"])
        self.assertTrue(qualify_rule(self.rule, self.splits["qualification"], [])["accepted"])
        self.assertFalse(qualify_rule(self.rule, [], [])["accepted"])

    def test_missing_qualification_labels_cannot_be_treated_as_evidence(self):
        invalid = [replace(case, expected=None) for case in self.splits["qualification"]]
        self.assertFalse(qualify_rule(self.rule, invalid, [])["accepted"])

    def test_same_rule_is_not_retrieved_for_unseen_revision(self):
        case = next(case for case in self.splits["transfer"] if case.category == "unseen-revision")
        model = ScriptedTestModel([{"role": "assistant", "content": "Cannot complete."}])
        result = run_agent(model, case, [self.rule], 1, "test")
        self.assertEqual(result["memory"], [])
        self.assertIsNone(self.rule.apply(case))

    def test_common_structure_but_different_validation_selection_and_persistence(self):
        wrong = replace(self.rule, offset=self.offset + 1)
        gate = qualify_rule(wrong, self.splits["qualification"], [])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "memory.db"
            bank = MemoryBank(path)
            bank.save(0, wrong, gate)
            bank.close()
            bank = MemoryBank(path)
            try:
                self.assertEqual(bank.load(0, "no_memory"), [])
                self.assertEqual(bank.load(0, "unvalidated_memory"), [wrong])
                self.assertEqual(bank.load(0, "validated_memory"), [])
            finally:
                bank.close()

    def test_remote_endpoint_cloud_model_and_credentials_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for endpoint in ("https://api.openai.com", "http://example.com:11434", "http://127.0.0.1@evil.example", "http://user:password@127.0.0.1:11434"):
                with self.assertRaises(ValueError):
                    LocalModel(Path(tmp), endpoint=endpoint)

    def test_split_duplicate_is_rejected_even_with_changed_case_id(self):
        duplicate = replace(self.case, id="changed-id")
        with self.assertRaises(ValueError):
            assert_connector_disjoint({"training": [self.case], "transfer": [duplicate]})

    def test_equal_budget_limits_stop_unbounded_model_tool_loop(self):
        model = ScriptedTestModel([tool("read_calibration") for _ in range(10)])
        result = run_agent(model, self.case, [], 1, "test", max_calls=2, max_tools=1)
        self.assertEqual(result["model_calls"], 2)
        self.assertEqual(result["tool_calls"], 1)
        self.assertFalse(result["grade"]["passed"])

    def test_captured_replay_checks_request_and_uses_no_live_model(self):
        response = {"done": True, "done_reason": "stop", "message": {"role": "assistant", "content": "Nothing done."}}
        requests = {7: {"body": {"messages": [{"role": "user", "content": "same"}], "options": {"seed": 1}}}}
        captured = CapturedModel([7], requests, {7: {"response": response}})
        self.assertEqual(captured.chat(requests[7]["body"]["messages"], 1, "test"), response)
        captured = CapturedModel([7], requests, {7: {"response": response}})
        with self.assertRaises(ValueError):
            captured.chat([{"role": "user", "content": "changed"}], 1, "test")


if __name__ == "__main__":
    unittest.main()
