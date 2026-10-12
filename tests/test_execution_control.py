from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experience_forge.connector_tasks import ConnectorCase
from experience_forge.execution_world import ExecutionWorld, infer_calibration, make_execution_splits
from experience_forge.execution_benchmark import reference_solve, execute_agent, run_execution_comparison, verify_execution


class ControlModel:
    """Contract test control, excluded from real experiment claims."""
    def __init__(self, output=None, *args, **kwargs):
        self.calls = 0
        self.tokens = {"input": 0, "output": 0}
        self.output = output

    def chat(self, messages, seed, tag, *, tools=False, schema=None, tool_definitions=None):
        import json
        from experience_forge.core import canonical
        self.calls += 1
        if schema:
            episodes = json.loads(messages[-1]["content"])
            case = episodes[0]["public_input"]
            derived = next(event["result"] for event in episodes[0]["tool_events"] if event["tool"] == "derive_calibration_rule")
            message = {"role": "assistant", "content": canonical({"source": case["source"], "revision": case["revision"], "scale": derived["scale"], "offset": derived["offset"]})}
        else:
            task = json.loads(messages[1]["content"])["task"]
            tool_messages = [message for message in messages if message["role"] == "tool"]
            if task["encoded_quantity"] is None:
                message = {"role": "assistant", "content": "Missing input; nothing saved."}
            elif not tool_messages:
                message = action("derive_calibration_rule")
            else:
                last = tool_messages[-1]
                result = json.loads(last["content"])
                if "error" in result:
                    message = {"role": "assistant", "content": "Unsupported input; nothing saved."}
                elif last["tool_name"] == "derive_calibration_rule":
                    message = action("normalize_quantity", scale=result["scale"], offset=result["offset"])
                elif last["tool_name"] == "normalize_quantity":
                    message = action("save_quantity", quantity=result["quantity"])
                elif last["tool_name"] == "save_quantity":
                    message = action("read_saved_quantity")
                else:
                    message = {"role": "assistant", "content": "Saved and verified."}
        response = {"message": message, "done": True, "done_reason": "stop", "model": "test-control", "prompt_eval_count": 10, "eval_count": 5}
        self.tokens["input"] += 10
        self.tokens["output"] += 5
        if self.output:
            body = {"model": "test-control", "messages": messages, "options": {"seed": seed}, "tools": tool_definitions} if tools else {"model": "test-control", "messages": messages, "options": {"seed": seed}, "format": schema}
            from experience_forge.agent_benchmark import append
            append(self.output / "model-calls.jsonl", {"event": "request", "call_id": self.calls, "tag": tag, "body": body})
            append(self.output / "model-calls.jsonl", {"event": "response", "call_id": self.calls, "tag": tag, "response": response})
        return response

    def preflight(self):
        return {"model": {"name": "test-control", "digest": "test-control"}, "runtime": {"version": "test"}}


def action(name, **arguments):
    return {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": name, "arguments": arguments}}]}


class ExecutionControlTests(unittest.TestCase):
    def setUp(self):
        self.case = ConnectorCase("opaque-id", "source", "r1", 141, ((-15, 0), (5, 10), (25, 20)), 78)

    def test_exact_derivation_handles_negative_offset_and_nonzero_calibration_origin(self):
        rule = infer_calibration(self.case)
        self.assertEqual((rule.scale, rule.offset), (2, -15))
        shifted = replace(self.case, examples=((9, 12), (19, 17)))
        self.assertEqual(infer_calibration(shifted), rule)

    def test_fractional_insufficient_duplicate_and_conflicting_observations_rejected(self):
        for pairs in (((0, 0),), ((0, 1), (10, 1)), ((0, 0), (1, 2)), ((0, 0), (20, 10), (41, 20))):
            with self.assertRaises(ValueError):
                infer_calibration(replace(self.case, examples=pairs))

    def test_guard_uses_public_evidence_not_hidden_expected_label(self):
        altered = replace(self.case, expected=9999)
        worlds = [ExecutionWorld(case, True) for case in (self.case, altered)]
        try:
            for name, args in (("derive_calibration_rule", {}), ("normalize_quantity", {"scale": 2, "offset": -15}), ("save_quantity", {"quantity": 78})):
                self.assertEqual(worlds[0].execute(name, args), worlds[1].execute(name, args))
            self.assertEqual(worlds[0].committed_writes, 1)
            self.assertEqual(worlds[1].committed_writes, 1)
        finally:
            for world in worlds:
                world.close()

    def test_guard_blocks_guess_without_normalization_then_allows_evidence_based_recovery(self):
        world = ExecutionWorld(self.case, True)
        try:
            self.assertIn("error", world.execute("save_quantity", {"quantity": 78}))
            self.assertEqual(world.committed_writes, 0)
            world.execute("normalize_quantity", {"scale": 2, "offset": -15})
            world.execute("save_quantity", {"quantity": 78})
            world.execute("read_saved_quantity", {})
            grade = world.grade(True)
            self.assertTrue(grade["passed"])
            self.assertFalse(grade["clean_completion"])
            self.assertEqual(grade["unsafe_write_attempts"], 1)
            self.assertEqual(grade["blocked_writes"], 1)
        finally:
            world.close()

    def test_matched_guard_control_exposes_wrong_commits_without_hiding_attempts(self):
        worlds = [ExecutionWorld(self.case, flag) for flag in (False, True)]
        try:
            for world in worlds:
                world.execute("normalize_quantity", {"scale": 2, "offset": 15})
                world.execute("save_quantity", {"quantity": 63})
                world.execute("read_saved_quantity", {})
            off, on = [world.grade(True) for world in worlds]
            self.assertEqual((off["wrong_write_commits"], on["wrong_write_commits"]), (1, 0))
            self.assertEqual((off["unsafe_write_attempts"], on["unsafe_write_attempts"]), (1, 1))
        finally:
            for world in worlds:
                world.close()

    def test_value_cannot_differ_from_supported_normalization(self):
        world = ExecutionWorld(self.case, True)
        try:
            world.execute("normalize_quantity", {"scale": 2, "offset": -15})
            self.assertIn("error", world.execute("save_quantity", {"quantity": 79}))
            self.assertEqual(world.committed_writes, 0)
        finally:
            world.close()

    def test_failed_normalization_invalidates_an_earlier_valid_proof(self):
        world = ExecutionWorld(self.case, True)
        try:
            world.execute("normalize_quantity", {"scale": 2, "offset": -15})
            world.execute("normalize_quantity", {"scale": 0, "offset": -15})
            self.assertIn("error", world.execute("save_quantity", {"quantity": 78}))
        finally:
            world.close()

    def test_source_revision_raw_and_calibration_changes_invalidate_proof(self):
        for change in ({"source": "other"}, {"revision": "r2"}, {"raw": 143}, {"examples": ((-15, 0), (7, 10))}):
            world = ExecutionWorld(self.case, True)
            try:
                world.execute("normalize_quantity", {"scale": 2, "offset": -15})
                world.case = replace(self.case, **change)
                self.assertIn("error", world.execute("save_quantity", {"quantity": 78}))
            finally:
                world.close()

    def test_repeated_commit_is_blocked_and_counted(self):
        world = ExecutionWorld(self.case, True)
        try:
            world.execute("normalize_quantity", {"scale": 2, "offset": -15})
            world.execute("save_quantity", {"quantity": 78})
            self.assertIn("error", world.execute("save_quantity", {"quantity": 78}))
            self.assertEqual(world.committed_writes, 1)
            self.assertEqual(world.unsafe_write_attempts, 1)
        finally:
            world.close()

    def test_missing_and_conflicting_inputs_remain_unsaved(self):
        for case in (replace(self.case, raw=None, expected=None), replace(self.case, examples=((-15, 0), (5, 10), (26, 20)), expected=None)):
            world = ExecutionWorld(case, True)
            try:
                self.assertIn("error", world.execute("derive_calibration_rule", {}))
                world.execute("normalize_quantity", {"scale": 2, "offset": -15})
                self.assertIn("error", world.execute("save_quantity", {"quantity": 78}))
                self.assertEqual(world.committed_writes, 0)
            finally:
                world.close()

    def test_ids_do_not_leak_partition_or_expected_abstention(self):
        splits = make_execution_splits(777)
        for cases in splits.values():
            for case in cases:
                self.assertRegex(case.id, r"^case-[0-9a-f]{16}$")
                self.assertNotIn("conflict", case.public()["revision"])

    def test_reference_solves_all_new_cases_using_only_available_tools(self):
        for seed in range(20):
            for case in make_execution_splits(seed)["transfer"]:
                result = reference_solve(case)
                self.assertTrue(result["grade"]["passed"])
                self.assertEqual(result["model_calls"], 0)

    def test_full_control_run_has_balanced_cells_and_model_free_independent_replay(self):
        with tempfile.TemporaryDirectory() as tmp, patch("experience_forge.execution_benchmark.LocalModel", ControlModel):
            output = Path(tmp) / "run"
            report = run_execution_comparison(output, seed=777, trials=1, model_name="test-control")
            self.assertEqual(len(report["results"]["conditions"]), 6)
            self.assertTrue(all(cell["total"] == 9 for cell in report["results"]["conditions"].values()))
            verified = verify_execution(output)
            self.assertEqual(verified["transfer_rollouts"], 54)
            self.assertEqual(verified["new_model_calls"], 0)
            with self.assertRaises(FileExistsError):
                run_execution_comparison(output, seed=777, trials=1, model_name="test-control")

    def test_endpoint_rejection_occurs_before_creating_any_output_or_storing_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "no-output"
            with self.assertRaises(ValueError):
                run_execution_comparison(output, endpoint="http://user:password@127.0.0.1:11434")
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
