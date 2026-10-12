"""Frozen outage pilot with durable experience, observed use and offline replay."""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import random
import statistics
import time

from .agent_benchmark import VARIANTS, SEMANTIC_FIELDS, CapturedModel, append, source_hashes
from .connector_tasks import AffineRule, qualify_rule
from .core import canonical
from .execution_benchmark import progress
from .local_agent import LocalModel, run_agent, propose_from_episodes, RULE_SCHEMA
from .reuse_world import ExperienceBank, ReuseWorld, REUSE_SYSTEM, REUSE_TOOLS, make_reuse_splits, make_item, check_observations


def execute_reuse(model, case, items, seed, tag, max_calls=8, max_tools=12):
    # No coefficients or observation lists are injected into the initial prompt.
    return run_agent(model, case, [], seed, tag, max_calls, max_tools,
        world_factory=lambda item: ReuseWorld(item, items), system=REUSE_SYSTEM, tool_definitions=REUSE_TOOLS)


def observed_episode(row):
    return {key: row[key] for key in ('case_id', 'public_input', 'tool_events', 'final')}


def qualify_item(rule, item, splits):
    gate = qualify_rule(rule, splits['qualification'], [])
    try:
        check_observations(rule, item['observations'])
        gate['observed_evidence_consistent'] = True
    except ValueError:
        gate['observed_evidence_consistent'] = False
        gate['accepted'] = False
        gate['reason'] = 'Absent or conflicting observed learning evidence'
    return gate


def summarize_reuse(rows):
    indexed = {(r['trial'], r['case_id'], r['variant']): r for r in rows}
    if len(indexed) != len(rows):
        raise ValueError('Duplicate comparison row')
    cells = {}
    for variant in VARIANTS:
        selected = [r for r in rows if r['variant'] == variant]
        primary = [r for r in selected if r['category'] == 'known-outage']
        cell = {'total': len(selected), 'successful': sum(r['grade']['passed'] for r in selected),
            'primary_reuse_denominator': len(primary)}
        for metric in ('retrieved_any', 'attempted_reuse', 'reused_any', 'correct_reuse_commit'):
            cell['primary_' + metric] = sum(r['grade'][metric] for r in primary)
        for metric in ('wrong_write_commits', 'unsafe_write_attempts', 'blocked_writes', 'appropriate_abstention',
                       'unsupported_abstention', 'calibration_reads', 'exact_derivations', 'memory_retrievals', 'memory_use_attempts', 'supported_reuse', 'failed_normalizations'):
            cell[metric] = sum(r['grade'][metric] for r in selected)
        for metric in ('model_calls', 'tool_calls', 'input_tokens', 'output_tokens', 'wall_seconds'):
            cell[metric] = sum(r[metric] for r in selected)
        cell['by_category'] = {category: {'total': sum(r['category'] == category for r in selected),
            'successful': sum(r['grade']['passed'] for r in selected if r['category'] == category)}
            for category in sorted({r['category'] for r in selected})}
        cell['per_seed'] = [{'seed': rows_for_seed[0]['seed'], 'successful': sum(r['grade']['passed'] for r in rows_for_seed),
            'total': len(rows_for_seed), 'primary_reuse': sum(r['grade']['reused_any'] for r in rows_for_seed if r['category'] == 'known-outage'),
            'primary_denominator': sum(r['category'] == 'known-outage' for r in rows_for_seed)}
            for trial in sorted({r['trial'] for r in selected})
            for rows_for_seed in [[r for r in selected if r['trial'] == trial]]]
        cells[variant] = cell
    paired = {}
    for variant in VARIANTS[1:]:
        selected = [r for r in rows if r['variant'] == variant]
        deltas = [int(r['grade']['passed']) - int(indexed[r['trial'], r['case_id'], 'no_memory']['grade']['passed']) for r in selected]
        per_seed = [sum(int(r['grade']['passed']) - int(indexed[r['trial'], r['case_id'], 'no_memory']['grade']['passed'])
            for r in selected if r['trial'] == trial) / 12 for trial in sorted({r['trial'] for r in selected})]
        paired[variant] = {'wins': sum(d > 0 for d in deltas), 'losses': sum(d < 0 for d in deltas), 'ties': sum(d == 0 for d in deltas),
            'seed_completion_rate_differences': per_seed, 'mean_seed_difference': statistics.mean(per_seed),
            'seed_difference_range': [min(per_seed), max(per_seed)],
            'seed_sample_sd': statistics.stdev(per_seed) if len(per_seed) > 1 else None,
            'independent_units': len(per_seed), 'uncertainty': 'Descriptive seed variation only; five authored datasets do not establish superiority or generalization.'}
    return {'variants': cells, 'paired_vs_no_memory': paired}


def reference_reuse(case, items):
    world = ReuseWorld(case, items)
    try:
        if case.raw is not None:
            recalled = world.execute('recall_experience', {})['items']
            matched = [item for item in recalled if item['rule']['revision'] == case.revision]
            if matched:
                rule = matched[0]['rule']
                result = world.execute('normalize_quantity', {'scale': rule['scale'], 'offset': rule['offset'], 'memory_id': matched[0]['id']})
            else:
                rule = world.execute('derive_calibration_rule', {})
                result = world.execute('normalize_quantity', {'scale': rule['scale'], 'offset': rule['offset']}) if 'error' not in rule else rule
            if not result.get('supported') and matched:
                fresh = world.execute('derive_calibration_rule', {})
                if 'error' not in fresh:
                    result = world.execute('normalize_quantity', {'scale': fresh['scale'], 'offset': fresh['offset']})
            if result.get('supported'):
                world.execute('save_quantity', {'quantity': result['quantity']})
                world.execute('read_saved_quantity', {})
        return {'case_id': case.id, 'grade': world.grade(True), 'tool_events': world.events, 'model_calls': 0}
    finally:
        world.close()


def run_reuse_comparison(destination, seed=60701, trials=5, model_name='qwen3.5:4b', endpoint='http://127.0.0.1:11434'):
    if not 1 <= trials <= 10:
        raise ValueError('Trials must be between 1 and 10')
    model = LocalModel(destination, model_name, endpoint, max_calls=trials * (3 * 8 + 3 + 12 * 3 * 8))
    destination.mkdir(parents=True, exist_ok=False)
    datasets = {str(trial): make_reuse_splits(seed + trial) for trial in range(trials)}
    protocol = {'version': '0.4.0', 'seed': seed, 'trials': trials, 'model': model_name,
        'max_calls_per_rollout': 8, 'max_tools_per_rollout': 12,
        'system': REUSE_SYSTEM, 'tools': REUSE_TOOLS, 'proposal_schema': RULE_SCHEMA,
        'source_hashes': source_hashes(), 'variants': list(VARIANTS), 'paid_api_allowed': False,
        'definition': 'Explicit retrieval ID/hash + matching new input + evidence-consistent candidate normalization without fresh calibration. Successful commit is separate.',
        'primary_denominator': 'six known-contract outage tasks per seed; other categories reported separately',
        'restart': 'new conversation and isolated SQLite world each rollout; treatment memory reopened read-only each rollout',
        'qualification': 'two independent numeric fixtures per regular contract plus observed-evidence consistency; no final labels',
        'shared_learning': 'three training episodes and three actual model proposals per seed; collected once, charged equally',
        'scoring': 'same desired stored state across treatments; unsupported abstention kept separate; empty correct state required on unsafe contracts',
        'uncertainty': 'seeds are independent units; descriptive range and sample SD; no superiority inference',
        'information_boundaries': {'initial_prompt': 'current public input, formula, generic instructions; no candidate rules or historical observations',
            'memory_tool': 'only reopened treatment items for current source; version mismatch visible',
            'fresh_tools': 'current visible calibration or unavailable; no historical fallback',
            'guard': 'explicitly retrieved evidence or previously read fresh evidence; verify chosen rule, never derive/repair or use gold',
            'grader': 'hidden target and category after rollout only'}}
    (destination / 'protocol.json').write_text(canonical(protocol))
    frozen = {trial: {name: [asdict(c) for c in cases] for name, cases in splits.items()} for trial, splits in datasets.items()}
    (destination / 'fixtures.json').write_text(canonical(frozen))
    bank = ExperienceBank(destination / 'experience.sqlite3')
    records, finals, proposals, gates, references = [], [], [], [], []
    started = time.monotonic()
    total = trials * 36
    progress(destination, {'status': 'in_progress', 'completed': 0, 'total': total})
    try:
        runtime = model.preflight()
        (destination / 'runtime.json').write_text(canonical(runtime))
        for trial in range(trials):
            splits = datasets[str(trial)]
            training = []
            for case in splits['training']:
                row = execute_reuse(model, case, [], seed + trial, f'trial-{trial}/training/{case.id}')
                row.update({'phase': 'training', 'trial': trial, 'seed': seed + trial, 'variant': 'shared'})
                training.append(row)
                records.append(row)
                append(destination / 'rollouts.jsonl', row)
            for case, episode in zip(splits['training'], training, strict=True):
                rule, proposal = propose_from_episodes(model, [observed_episode(episode)], seed + trial, f'trial-{trial}/proposal/{case.id}')
                if rule is not None and (rule.source, rule.revision) != (case.source, case.revision):
                    rule = None
                    proposal.update({'structurally_valid': False, 'error': 'Proposed scope differs from observed contract'})
                proposal.update({'trial': trial, 'case_id': case.id})
                proposals.append(proposal)
                append(destination / 'proposals.jsonl', proposal)
                if rule is not None:
                    item = make_item(rule, episode)
                    gate_start = time.monotonic()
                    gate = qualify_item(rule, item, splits)
                    gate.update({'trial': trial, 'item': item, 'wall_seconds': time.monotonic() - gate_start, 'model_calls': 0})
                    gates.append(gate)
                    append(destination / 'gates.jsonl', gate)
                    bank.save(trial, item, gate['accepted'])
            bank.close()
            bank = ExperienceBank(destination / 'experience.sqlite3')
            cases = list(splits['transfer'])
            random.Random(seed + trial).shuffle(cases)
            for ordinal, case in enumerate(cases):
                rotation = (trial + ordinal) % 3
                for variant in VARIANTS[rotation:] + VARIANTS[:rotation]:
                    reopened = ExperienceBank(destination / 'experience.sqlite3', read_only=True)
                    try:
                        items = reopened.load(trial, variant)
                    finally:
                        reopened.close()
                    row = execute_reuse(model, case, items, seed + trial, f'trial-{trial}/{variant}/{case.id}')
                    row.update({'phase': 'transfer', 'trial': trial, 'seed': seed + trial, 'variant': variant,
                        'ordinal': ordinal, 'memory_snapshot': items})
                    finals.append(row)
                    records.append(row)
                    append(destination / 'rollouts.jsonl', row)
                    references.append({'trial': trial, 'variant': variant, **reference_reuse(case, items)})
                    progress(destination, {'status': 'in_progress', 'completed': len(finals), 'total': total, 'model_calls': model.calls})
                print(f'Dataset {trial+1}/{trials}, task {ordinal+1}/12: {len(finals)}/{total} final rollouts', flush=True)
        if source_hashes() != protocol['source_hashes']:
            raise ValueError('Frozen source changed during the experiment')
        events = read_lines(destination / 'model-calls.jsonl')
        proposal_ids = {p['call_id'] for p in proposals}
        learning_responses = [e['response'] for e in events if e['event'] == 'response' and
            (e['call_id'] in proposal_ids or '/training/' in e['tag'])]
        report = {'version': '0.4.0', 'status': 'complete', 'protocol': protocol, 'runtime': runtime,
            'results': summarize_reuse(finals), 'total_actual_model_calls': model.calls, 'total_actual_tokens': model.tokens,
            'paid_api_calls': 0, 'remote_network_requests': 0, 'local_http_requests': model.calls + 3,
            'shared_learning': {'episodes': trials * 3, 'proposals': len(proposals), 'model_calls': len(learning_responses),
                'input_tokens': sum(r.get('prompt_eval_count', 0) for r in learning_responses),
                'output_tokens': sum(r.get('eval_count', 0) for r in learning_responses),
                'allocation': 'physically collected once; same cost assigned to every treatment'},
            'qualification': {'accepted': sum(g['accepted'] for g in gates), 'rejected': sum(not g['accepted'] for g in gates),
                'structurally_invalid': sum(not p['structurally_valid'] for p in proposals), 'model_calls': 0,
                'wall_seconds': sum(g['wall_seconds'] for g in gates),
                'cases_evaluated': sum(len(g['rows']) for g in gates)},
            'reference': {'scope': 'scripted same-information controls; excluded from actual model scores',
                'by_variant': {v: {'total': sum(r['variant'] == v for r in references),
                    'successful': sum(r['grade']['passed'] for r in references if r['variant'] == v)} for v in VARIANTS}, 'model_calls': 0},
            'restart_verified': True, 'wall_seconds': time.monotonic() - started,
            'limitations': ['Authored affine family and one local model; supplied functional form and exact arithmetic.',
                'Memory supplies missing information. No-memory outage tasks lack sufficient evidence; this is part of the intervention, not proof of general intelligence.',
                'Observed retrieval and use are external behavior; no claim about hidden cognition or weight updates.',
                'Shared write protection can mask invalid memories at the commit stage; failed normalization and blocked attempts remain visible.',
                'Five seeds are a pilot; seed variation is descriptive, not a confidence bound or independent replication.',
                'Tools, prompts and limits match; realized cost, token and cache/order effects may differ.',
                'Jev design review cost is separate; no new paid API requests in this benchmark.',
                'Native Windows benchmark, browser rendering, other models and hosted CI remain unverified.']}
        (destination / 'reference.json').write_text(canonical(references))
        (destination / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        from .reuse_report import render_reuse
        (destination / 'report.html').write_text(render_reuse(report))
        progress(destination, {'status': 'complete', 'completed': len(finals), 'total': total, 'model_calls': model.calls})
        bank.close()
        bank = None
        manifest = {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(destination.iterdir()) if p.is_file()}
        (destination / 'manifest.json').write_text(canonical(manifest))
        return report
    except Exception as error:
        progress(destination, {'status': 'incomplete', 'completed': len(finals), 'total': total,
            'error': str(error), 'retry': False, 'model_calls_started': model.calls, 'recorded_tokens': model.tokens})
        raise
    finally:
        if bank is not None:
            bank.close()


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def verify_reuse(destination):
    manifest = json.loads((destination / 'manifest.json').read_text())
    required = {'protocol.json', 'fixtures.json', 'runtime.json', 'experience.sqlite3', 'rollouts.jsonl', 'proposals.jsonl',
        'model-calls.jsonl', 'report.json', 'report.html', 'reference.json', 'progress.json'}
    if not required <= set(manifest) or set(manifest) - required - {'gates.jsonl'}:
        raise ValueError('Unexpected evidence inventory')
    for name, digest in manifest.items():
        if Path(name).name != name or sha256((destination / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Evidence changed: ' + name)
    report = json.loads((destination / 'report.json').read_text())
    protocol = json.loads((destination / 'protocol.json').read_text())
    if report['protocol'] != protocol or protocol['source_hashes'] != source_hashes() or protocol['system'] != REUSE_SYSTEM or protocol['tools'] != REUSE_TOOLS:
        raise ValueError('Replay requires the original frozen source and protocol')
    datasets = {str(t): make_reuse_splits(protocol['seed'] + t) for t in range(protocol['trials'])}
    frozen = {t: {name: [asdict(c) for c in cases] for name, cases in splits.items()} for t, splits in datasets.items()}
    if canonical(frozen) != (destination / 'fixtures.json').read_text():
        raise ValueError('Regenerated fixtures and labels differ')
    events = read_lines(destination / 'model-calls.jsonl')
    requests = {e['call_id']: e for e in events if e['event'] == 'request'}
    responses = {e['call_id']: e for e in events if e['event'] == 'response'}
    if len(events) != 2 * len(requests) or set(requests) != set(responses) or set(requests) != set(range(1, len(requests) + 1)):
        raise ValueError('Duplicate, incomplete or failed captured calls')
    tokens = {'input': sum(e['response'].get('prompt_eval_count', 0) for e in responses.values()),
        'output': sum(e['response'].get('eval_count', 0) for e in responses.values())}
    if len(requests) != report['total_actual_model_calls'] or tokens != report['total_actual_tokens']:
        raise ValueError('Model-call consumption differs')
    records = read_lines(destination / 'rollouts.jsonl')
    finals = [r for r in records if r['phase'] == 'transfer']
    proposals = read_lines(destination / 'proposals.jsonl')
    if len(records) != protocol['trials'] * 39 or len(proposals) != protocol['trials'] * 3:
        raise ValueError('Missing or extra training/final/proposal records')
    used_ids = [cid for row in records for cid in row['call_ids']] + [p['call_id'] for p in proposals]
    if len(used_ids) != len(set(used_ids)) or set(used_ids) != set(requests):
        raise ValueError('Unassigned or duplicated inference provenance')
    expected_memory = {}
    expected_gates = []
    for trial in range(protocol['trials']):
        splits = datasets[str(trial)]
        expected_memory[trial] = {v: [] for v in VARIANTS}
        training = [r for r in records if r['trial'] == trial and r['phase'] == 'training']
        if len(training) != 3 or {r['case_id'] for r in training} != {c.id for c in splits['training']}:
            raise ValueError('Training scopes differ')
        trial_proposals = [p for p in proposals if p['trial'] == trial]
        if len(trial_proposals) != 3 or {p['case_id'] for p in trial_proposals} != {c.id for c in splits['training']}:
            raise ValueError('Proposal scopes differ')
        for proposal in trial_proposals:
            episode = next(r for r in training if r['case_id'] == proposal['case_id'])
            captured = CapturedModel([proposal['call_id']], requests, responses)
            if requests[proposal['call_id']]['body'].get('format') != RULE_SCHEMA:
                raise ValueError('Proposal schema differs')
            rule, replay = propose_from_episodes(captured, [observed_episode(episode)], protocol['seed'] + trial, 'replay')
            public = episode['public_input']
            if rule is not None and (rule.source, rule.revision) != (public['source'], public['revision']):
                rule = None
                replay.update({'structurally_valid': False, 'error': 'Proposed scope differs from observed contract'})
            replay.update({'trial': trial, 'case_id': episode['case_id']})
            if replay != proposal:
                raise ValueError('Actual model proposal replay differs')
            if rule is not None:
                item = make_item(rule, episode)
                gate = qualify_item(rule, item, splits)
                gate.update({'trial': trial, 'item': item, 'model_calls': 0})
                expected_gates.append(gate)
                expected_memory[trial]['unvalidated_memory'].append(item)
                if gate['accepted']:
                    expected_memory[trial]['validated_memory'].append(item)
        for variant in VARIANTS:
            cell = [r for r in finals if r['trial'] == trial and r['variant'] == variant]
            if len(cell) != 12 or {r['case_id'] for r in cell} != {c.id for c in splits['transfer']}:
                raise ValueError('Unbalanced matched comparison')
    recorded_gates = read_lines(destination / 'gates.jsonl')
    if expected_gates != [{k: v for k, v in g.items() if k != 'wall_seconds'} for g in recorded_gates]:
        raise ValueError('Qualification or provenance differs')
    qualification = {'accepted': sum(g['accepted'] for g in recorded_gates),
        'rejected': sum(not g['accepted'] for g in recorded_gates),
        'structurally_invalid': sum(not p['structurally_valid'] for p in proposals),
        'model_calls': 0, 'wall_seconds': sum(g['wall_seconds'] for g in recorded_gates),
        'cases_evaluated': sum(len(g['rows']) for g in recorded_gates)}
    if report['qualification'] != qualification:
        raise ValueError('Reported qualification consumption or results differ')
    bank = ExperienceBank(destination / 'experience.sqlite3', read_only=True)
    references = []
    try:
        for trial, treatments in expected_memory.items():
            for variant, items in treatments.items():
                if bank.load(trial, variant) != sorted(items, key=lambda item: item['id']):
                    raise ValueError('Reopened memory differs from observed proposals')
        for row in records:
            case = next(c for c in datasets[str(row['trial'])][row['phase']] if c.id == row['case_id'])
            items = [] if row['phase'] == 'training' else bank.load(row['trial'], row['variant'])
            if row['phase'] == 'transfer' and items != row['memory_snapshot']:
                raise ValueError('Treatment memory snapshot differs')
            captured = CapturedModel(row['call_ids'], requests, responses)
            replay = execute_reuse(captured, case, items, protocol['seed'] + row['trial'], 'replay')
            if captured.ids or any(canonical(replay[k]) != canonical(row[k]) for k in SEMANTIC_FIELDS):
                raise ValueError('World and actual decision replay differs: ' + case.id)
            if row['phase'] == 'transfer':
                references.append({'trial': row['trial'], 'variant': row['variant'], **reference_reuse(case, items)})
    finally:
        bank.close()
    if canonical(references) != (destination / 'reference.json').read_text() or summarize_reuse(finals) != report['results']:
        raise ValueError('Reference controls or paired outcome summaries differ')
    expected_reference = {'scope': 'scripted same-information controls; excluded from actual model scores',
        'by_variant': {v: {'total': sum(r['variant'] == v for r in references),
            'successful': sum(r['grade']['passed'] for r in references if r['variant'] == v)} for v in VARIANTS}, 'model_calls': 0}
    if report['reference'] != expected_reference or report['paid_api_calls'] != 0 or report['remote_network_requests'] != 0:
        raise ValueError('Reported reference or provider accounting differs')
    shared = [e['response'] for e in responses.values() if '/training/' in e['tag'] or e['call_id'] in {p['call_id'] for p in proposals}]
    if (len(shared), sum(r.get('prompt_eval_count', 0) for r in shared), sum(r.get('eval_count', 0) for r in shared)) != tuple(report['shared_learning'][k] for k in ('model_calls', 'input_tokens', 'output_tokens')):
        raise ValueError('Common-phase usage differs')
    return {'model_rollouts_replayed': len(records), 'transfer_rollouts': len(finals), 'model_calls_verified': len(requests),
        'reference_controls_replayed': len(references), 'new_model_calls': 0, 'new_remote_requests': 0}
