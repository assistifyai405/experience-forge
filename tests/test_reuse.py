from copy import deepcopy
from dataclasses import replace, asdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experience_forge.agent_benchmark import append
from experience_forge.connector_tasks import AffineRule, ConnectorCase
from experience_forge.core import canonical
from experience_forge.reuse_world import ReuseWorld, ExperienceBank, make_item, make_reuse_splits, item_intact
from experience_forge.reuse_benchmark import run_reuse_comparison, verify_reuse


def action(name, **args):
    return {'role': 'assistant', 'content': '', 'tool_calls': [{'function': {'name': name, 'arguments': args}}]}


class ReuseControlModel:
    """Scripted integration control only; never counted as live model quality."""
    def __init__(self, output=None, *args, **kwargs):
        self.output = output
        self.calls = 0
        self.tokens = {'input': 0, 'output': 0}

    def preflight(self):
        return {'model': {'name': 'test-control', 'digest': 'test-control'}, 'runtime': {'version': 'test'}}

    def chat(self, messages, seed, tag, tools=False, schema=None, tool_definitions=None):
        self.calls += 1
        if schema:
            episode = json.loads(messages[-1]['content'])[0]
            observed = next(e['result'] for e in episode['tool_events'] if e['tool'] == 'derive_calibration_rule')
            pairs = observed['examples']
            scale = (pairs[1]['encoded'] - pairs[0]['encoded']) // (pairs[1]['quantity'] - pairs[0]['quantity'])
            rule = {key: episode['public_input'][key] for key in ('source', 'revision')}
            rule.update({'scale': scale, 'offset': pairs[0]['encoded'] - scale * pairs[0]['quantity']})
            message = {'role': 'assistant', 'content': canonical(rule)}
        else:
            task = json.loads(messages[1]['content'])['task']
            history = [m for m in messages if m['role'] == 'tool']
            if task['encoded_quantity'] is None:
                message = {'role': 'assistant', 'content': 'Missing input; nothing saved.'}
            elif not history:
                message = action('recall_experience')
            else:
                last = history[-1]
                result = json.loads(last['content'])
                name = last['tool_name']
                if 'error' in result:
                    message = {'role': 'assistant', 'content': 'Unsupported evidence; nothing saved.'}
                elif name == 'recall_experience':
                    matches = [item for item in result['items'] if item['rule']['revision'] == task['revision']]
                    if matches:
                        item = matches[0]
                        message = action('normalize_quantity', scale=item['rule']['scale'], offset=item['rule']['offset'], memory_id=item['id'])
                    else:
                        message = action('derive_calibration_rule')
                elif name == 'derive_calibration_rule':
                    message = action('normalize_quantity', scale=result['scale'], offset=result['offset'])
                elif name == 'normalize_quantity':
                    message = action('save_quantity', quantity=result['quantity'])
                elif name == 'save_quantity':
                    message = action('read_saved_quantity')
                else:
                    message = {'role': 'assistant', 'content': 'Saved and verified.'}
        response = {'model': 'test-control', 'done': True, 'done_reason': 'stop', 'message': message, 'prompt_eval_count': 10, 'eval_count': 5}
        self.tokens['input'] += 10
        self.tokens['output'] += 5
        body = {'model': 'test-control', 'messages': messages, 'options': {'seed': seed}}
        if tools:
            body['tools'] = tool_definitions
        if schema:
            body['format'] = schema
        append(self.output / 'model-calls.jsonl', {'event': 'request', 'call_id': self.calls, 'tag': tag, 'body': body})
        append(self.output / 'model-calls.jsonl', {'event': 'response', 'call_id': self.calls, 'tag': tag, 'response': response})
        return response


class ReuseTests(unittest.TestCase):
    def setUp(self):
        self.rule = AffineRule('sensor', 'r1', 2, -15)
        self.case = ConnectorCase('test-case', 'sensor', 'r1', 141, (), 78, 'known-outage')
        training = replace(self.case, id='training-case', raw=45)
        self.item = make_item(self.rule, {'case_id': training.id, 'public_input': training.public(),
            'tool_events': [{'tool': 'read_calibration', 'arguments': {}, 'result': {'examples': [{'encoded': -15, 'quantity': 0}, {'encoded': 5, 'quantity': 10}]}}]})

    def normalize(self, world):
        return world.execute('normalize_quantity', {'scale': 2, 'offset': -15, 'memory_id': self.item['id']})

    def test_implicit_lookup_prohibited_even_with_memory_present(self):
        world = ReuseWorld(self.case, [self.item])
        try:
            self.assertIn('error', self.normalize(world))
            self.assertIn('error', world.execute('normalize_quantity', {'scale': 2, 'offset': -15}))
            self.assertIn('error', world.execute('save_quantity', {'quantity': 78}))
            self.assertEqual(world.committed_writes, 0)
        finally:
            world.close()

    def test_observable_reuse_is_separate_from_correct_commit(self):
        world = ReuseWorld(self.case, [self.item])
        try:
            recalled = world.execute('recall_experience', {})['items'][0]
            self.assertEqual(recalled['content_hash'], self.item['content_hash'])
            self.assertTrue(self.normalize(world)['supported'])
            before = world.grade(True)
            self.assertTrue(before['reused_any'])
            self.assertFalse(before['correct_reuse_commit'])
            world.execute('save_quantity', {'quantity': 78})
            world.execute('read_saved_quantity', {})
            self.assertTrue(world.grade(True)['correct_reuse_commit'])
        finally:
            world.close()

    def test_hidden_label_changes_do_not_change_tools_or_guard(self):
        worlds = [ReuseWorld(c, [self.item]) for c in (self.case, replace(self.case, expected=1000))]
        try:
            for name, args in [('recall_experience', {}), ('normalize_quantity', {'scale': 2, 'offset': -15, 'memory_id': self.item['id']}), ('save_quantity', {'quantity': 78})]:
                self.assertEqual(worlds[0].execute(name, args), worlds[1].execute(name, args))
            self.assertNotEqual(worlds[0].grade(True)['expected'], worlds[1].grade(True)['expected'])
        finally:
            for world in worlds:
                world.close()

    def test_stale_version_retrieval_does_not_authorize_write(self):
        world = ReuseWorld(replace(self.case, revision='r2', expected=None), [self.item])
        try:
            self.assertEqual(len(world.execute('recall_experience', {})['items']), 1)
            self.assertIn('error', self.normalize(world))
            self.assertIn('error', world.execute('save_quantity', {'quantity': 78}))
            self.assertEqual(world.grade(True)['supported_reuse'], 0)
        finally:
            world.close()

    def test_no_memory_and_unavailable_fresh_calibration_supply_no_history(self):
        world = ReuseWorld(self.case, [])
        try:
            self.assertEqual(world.execute('recall_experience', {})['items'], [])
            self.assertIn('error', world.execute('derive_calibration_rule', {}))
            self.assertIsNone(world.fresh_observations)
            self.assertIn('error', world.execute('save_quantity', {'quantity': 78}))
        finally:
            world.close()

    def test_bad_candidate_not_silently_repaired(self):
        episode = {'case_id': 'train', 'public_input': replace(self.case, raw=45).public(),
            'tool_events': [{'tool': 'read_calibration', 'result': {'examples': self.item['observations']}}]}
        bad = make_item(AffineRule('sensor', 'r1', 3, -15), episode)
        world = ReuseWorld(self.case, [bad])
        try:
            world.execute('recall_experience', {})
            self.assertIn('error', world.execute('normalize_quantity', {'scale': 3, 'offset': -15, 'memory_id': bad['id']}))
            self.assertIn('error', world.execute('normalize_quantity', {'scale': 2, 'offset': -15, 'memory_id': bad['id']}))
            self.assertFalse(world.grade(True)['reused_any'])
        finally:
            world.close()

    def test_tampering_detected_and_reopened_memory_is_condition_scoped(self):
        altered = deepcopy(self.item)
        altered['observations'][0]['encoded'] += 1
        self.assertFalse(item_intact(altered))
        with self.assertRaises(ValueError):
            ReuseWorld(self.case, [altered])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'memory.sqlite3'
            bank = ExperienceBank(path)
            bank.save(0, self.item, False)
            bank.close()
            bank = ExperienceBank(path, read_only=True)
            try:
                self.assertEqual(bank.load(0, 'unvalidated_memory'), [self.item])
                self.assertEqual(bank.load(0, 'validated_memory'), [])
                self.assertEqual(bank.load(0, 'no_memory'), [])
                self.assertEqual(bank.load(1, 'unvalidated_memory'), [])
            finally:
                bank.close()

    def test_failed_normalization_and_changed_input_invalidate_proof(self):
        for change in ('failed', 'raw', 'revision', 'observations'):
            world = ReuseWorld(self.case, [self.item])
            try:
                world.execute('recall_experience', {})
                self.normalize(world)
                if change == 'failed':
                    world.execute('normalize_quantity', {'scale': 0, 'offset': -15})
                elif change == 'raw':
                    world.case = replace(self.case, raw=143)
                elif change == 'revision':
                    world.case = replace(self.case, revision='r2')
                else:
                    world.retrieved[self.item['id']]['observations'][0]['encoded'] += 1
                self.assertIn('error', world.execute('save_quantity', {'quantity': 78}))
                self.assertEqual(world.committed_writes, 0)
            finally:
                world.close()

    def test_missing_input_and_mismatched_quantity_never_commit(self):
        for case, quantity in ((replace(self.case, raw=None, expected=None), 78), (self.case, 79)):
            world = ReuseWorld(case, [self.item])
            try:
                world.execute('recall_experience', {})
                self.normalize(world)
                self.assertIn('error', world.execute('save_quantity', {'quantity': quantity}))
            finally:
                world.close()

    def test_conflicting_observations_block_normalization(self):
        item = deepcopy(self.item)
        episode = {'case_id': 'train', 'public_input': replace(self.case, raw=45).public(),
            'tool_events': [{'tool': 'read_calibration', 'result': {'examples': item['observations'] + [{'encoded': 26, 'quantity': 20}]}}]}
        item = make_item(self.rule, episode)
        world = ReuseWorld(self.case, [item])
        try:
            world.execute('recall_experience', {})
            self.assertIn('error', world.execute('normalize_quantity', {'scale': 2, 'offset': -15, 'memory_id': item['id']}))
        finally:
            world.close()

    def test_frozen_partitions_and_opaque_inputs(self):
        for seed in range(30):
            splits = make_reuse_splits(seed)
            self.assertEqual(len(splits['transfer']), 12)
            self.assertEqual(sum(c.category == 'known-outage' for c in splits['transfer']), 6)
            self.assertEqual(len(splits['training']), 3)
            for cases in splits.values():
                for case in cases:
                    self.assertRegex(case.id, r'^case-[a-f0-9]{16}$')
                    self.assertNotIn('category', case.public())
                    self.assertNotIn('expected', case.public())

    def test_balanced_scripted_control_and_model_free_replay(self):
        with tempfile.TemporaryDirectory() as tmp, patch('experience_forge.reuse_benchmark.LocalModel', ReuseControlModel):
            destination = Path(tmp) / 'run'
            report = run_reuse_comparison(destination, seed=90901, trials=1, model_name='test-control')
            cells = report['results']['variants']
            self.assertEqual(cells['no_memory']['successful'], 6)
            self.assertEqual(cells['unvalidated_memory']['successful'], 12)
            self.assertEqual(cells['validated_memory']['successful'], 12)
            self.assertEqual(cells['validated_memory']['primary_reused_any'], 6)
            verified = verify_reuse(destination)
            self.assertEqual(verified['transfer_rollouts'], 36)
            self.assertEqual(verified['new_model_calls'], 0)
            with self.assertRaises(FileExistsError):
                run_reuse_comparison(destination, trials=1, model_name='test-control')

    def test_invalid_endpoint_or_trial_count_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'run'
            for args in ({'trials': 0}, {'endpoint': 'http://127.0.0.1:11434@evil.invalid'}):
                with self.assertRaises(ValueError):
                    run_reuse_comparison(output, **args)
                self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
