"""Matched 3-memory × 2-write-control study with separately attributed outcomes."""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import random
import time

from .agent_benchmark import MemoryBank, CapturedModel, VARIANTS, SEMANTIC_FIELDS, append, source_hashes
from .connector_tasks import AffineRule, qualify_rule
from .core import canonical
from .execution_world import ExecutionWorld, EXECUTION_SYSTEM, EXECUTION_TOOLS, make_execution_splits
from .local_agent import LocalModel, run_agent, propose_from_episodes

MODES = ("guard_off", "guard_on")
CONDITIONS = tuple((mode, variant) for mode in MODES for variant in VARIANTS)


def execute_agent(model, case, memory, seed, tag, mode, max_calls=8, max_tools=12):
    if mode not in MODES:
        raise ValueError("Unknown execution mode")
    return run_agent(model, case, memory, seed, tag, max_calls, max_tools,
        world_factory=lambda item: ExecutionWorld(item, guard=mode == "guard_on"),
        system=EXECUTION_SYSTEM, tool_definitions=EXECUTION_TOOLS)


def reference_solve(case) -> dict:
    """Deterministic reference control; uses only the same visible observations."""
    world = ExecutionWorld(case, guard=True)
    try:
        if case.raw is not None:
            derived = world.execute("derive_calibration_rule", {})
            if "error" not in derived:
                normalized = world.execute("normalize_quantity", {"scale": derived["scale"], "offset": derived["offset"]})
                if normalized["supported"]:
                    world.execute("save_quantity", {"quantity": normalized["quantity"]})
                    world.execute("read_saved_quantity", {})
        return {"case_id": case.id, "grade": world.grade(True), "tool_events": world.events,
                "model_calls": 0, "tool_calls": len(world.events)}
    finally:
        world.close()


def summarize_execution(rows: list[dict]) -> dict:
    indexed = {(row["trial"], row["case_id"], row["mode"], row["variant"]): row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError("Duplicate matched rollout")
    cells, guard_effect, memory_effect = {}, {}, {}
    for mode, variant in CONDITIONS:
        selected = [row for row in rows if row["mode"] == mode and row["variant"] == variant]
        metrics = {"total": len(selected), "successful": sum(row["grade"]["passed"] for row in selected),
            "clean_completion": sum(row["grade"]["clean_completion"] for row in selected)}
        for key in ("wrong_write_commits", "unsafe_write_attempts", "blocked_writes", "committed_writes", "exact_derivations", "calibration_reads", "calibration_checks"):
            metrics[key] = sum(row["grade"][key] for row in selected)
        for key in ("model_calls", "tool_calls", "input_tokens", "output_tokens"):
            metrics[key] = sum(row[key] for row in selected)
        metrics["wall_seconds"] = round(sum(row["wall_seconds"] for row in selected), 6)
        metrics["per_trial"] = [{"trial": trial, "successful": sum(row["grade"]["passed"] for row in selected if row["trial"] == trial),
            "wrong_write_commits": sum(row["grade"]["wrong_write_commits"] for row in selected if row["trial"] == trial),
            "total": sum(row["trial"] == trial for row in selected)} for trial in sorted({row["trial"] for row in selected})]
        cells[f"{mode}/{variant}"] = metrics
    for variant in VARIANTS:
        wins = losses = ties = wrong_reduction = 0
        for row in (row for row in rows if row["variant"] == variant and row["mode"] == "guard_on"):
            old = indexed[row["trial"], row["case_id"], "guard_off", variant]
            delta = int(row["grade"]["passed"]) - int(old["grade"]["passed"])
            wins += delta > 0
            losses += delta < 0
            ties += delta == 0
            wrong_reduction += old["grade"]["wrong_write_commits"] - row["grade"]["wrong_write_commits"]
        guard_effect[variant] = {"completion_wins": wins, "completion_losses": losses, "completion_ties": ties,
            "wrong_commit_reduction": wrong_reduction}
    for mode in MODES:
        for variant in VARIANTS[1:]:
            wins = losses = ties = 0
            for row in (row for row in rows if row["mode"] == mode and row["variant"] == variant):
                baseline = indexed[row["trial"], row["case_id"], mode, "no_memory"]
                delta = int(row["grade"]["passed"]) - int(baseline["grade"]["passed"])
                wins += delta > 0
                losses += delta < 0
                ties += delta == 0
            memory_effect[f"{mode}/{variant}"] = {"completion_wins": wins, "completion_losses": losses, "completion_ties": ties}
    return {"conditions": cells, "paired_guard_effect": guard_effect, "paired_memory_effect": memory_effect}


def progress(destination: Path, value: dict):
    temporary = destination / "progress.tmp"
    temporary.write_text(canonical(value), encoding="utf-8")
    temporary.replace(destination / "progress.json")


def run_execution_comparison(destination: Path, seed=60601, trials=5, model_name="qwen3.5:4b", endpoint="http://127.0.0.1:11434") -> dict:
    if not 1 <= trials <= 10:
        raise ValueError("Trials must be between 1 and 10")
    max_calls, max_tools = 8, 12
    model = LocalModel(destination, model_name, endpoint, max_calls=trials * (2 * max_calls + 2 + 9 * 6 * max_calls))
    # Validate endpoint before writing its string into an artifact.
    destination.mkdir(parents=True, exist_ok=False)
    datasets = {str(trial): make_execution_splits(seed + trial) for trial in range(trials)}
    frozen = {trial: {name: [asdict(case) for case in cases] for name, cases in splits.items()} for trial, splits in datasets.items()}
    protocol = {"version": "0.3.0", "seed": seed, "trials": trials, "model": model_name,
        "max_calls_per_rollout": max_calls, "max_tools_per_rollout": max_tools,
        "temperature": 0, "num_ctx": 8192, "max_output_tokens_per_call": 256,
        "conditions": [[mode, variant] for mode, variant in CONDITIONS],
        "tools": EXECUTION_TOOLS, "system": EXECUTION_SYSTEM,
        "shared_training_mode": "guard_off/no_memory", "shared_training": "same observed episodes and model proposals in every condition",
        "selection": "only validated memory uses independent qualification labels; final labels are excluded",
        "write_control": "only guard_on requires a current supported normalization matching source, revision, input, calibration and value",
        "matched_comparison": "seeded case shuffle and rotating six-condition order; identical prompts, tools and budgets",
        "scoring": "actual committed state and readback; unsafe attempts measured separately from blocked or wrong commits",
        "math_helper": "exact Fraction arithmetic available in ALL six conditions; no isolated causal test of helper versus v0.2",
        "source_hashes": source_hashes(), "paid_api_allowed": False}
    (destination / "protocol.json").write_text(canonical(protocol), encoding="utf-8")
    (destination / "fixtures.json").write_text(canonical(frozen), encoding="utf-8")
    reference = [{"trial": trial, **reference_solve(case)} for trial in range(trials) for case in datasets[str(trial)]["transfer"]]
    (destination / "reference.json").write_text(canonical(reference), encoding="utf-8")
    bank = MemoryBank(destination / "memory.sqlite3")
    rollouts, training, proposals, gates = [], [], [], []
    started = time.monotonic()
    total = trials * 9 * 6
    progress(destination, {"status": "in_progress", "completed": 0, "total": total})
    try:
        metadata = model.preflight()
        (destination / "runtime.json").write_text(canonical(metadata), encoding="utf-8")
        for trial in range(trials):
            splits = datasets[str(trial)]
            for case in splits["training"]:
                row = execute_agent(model, case, [], seed + trial, f"trial-{trial}/training/{case.id}", "guard_off")
                row.update({"phase": "training", "trial": trial, "mode": "guard_off", "variant": "shared"})
                training.append(row)
                append(destination / "rollouts.jsonl", row)
                print(f"Dataset {trial+1}/{trials}: training {case.source}, success={row['grade']['passed']}", flush=True)
            for case in splits["training"]:
                episodes = [row for row in training if row["trial"] == trial and row["public_input"]["source"] == case.source]
                rule, proposal = propose_from_episodes(model, episodes, seed + trial, f"trial-{trial}/proposal/{case.source}")
                proposal.update({"trial": trial, "source": case.source, "revision": case.revision})
                if rule is not None and (rule.source, rule.revision) != (case.source, case.revision):
                    rule = None
                    proposal.update({"structurally_valid": False, "error": "Proposed scope differs from training"})
                proposals.append(proposal)
                append(destination / "proposals.jsonl", proposal)
                if rule is not None:
                    retained = [(old, item) for old in bank.load(trial, "validated_memory") for item in splits["qualification"]
                        if (old.source, old.revision) == (item.source, item.revision)]
                    gate_start = time.monotonic()
                    gate = qualify_rule(rule, splits["qualification"], retained)
                    gate.update({"trial": trial, "rule": asdict(rule), "model_calls": 0, "wall_seconds": round(time.monotonic() - gate_start, 9)})
                    gates.append(gate)
                    append(destination / "gates.jsonl", gate)
                    bank.save(trial, rule, gate)
                    print(f"  Rule {rule.source}: scale={rule.scale}, offset={rule.offset}, accepted={gate['accepted']}", flush=True)
            snapshot = {variant: [asdict(rule) for rule in bank.load(trial, variant)] for variant in VARIANTS}
            bank.close()
            bank = MemoryBank(destination / "memory.sqlite3")
            if snapshot != {variant: [asdict(rule) for rule in bank.load(trial, variant)] for variant in VARIANTS}:
                raise ValueError("Memory did not survive restart")
            cases = list(splits["transfer"])
            random.Random(seed + trial).shuffle(cases)
            for ordinal, case in enumerate(cases):
                rotation = (trial + ordinal) % len(CONDITIONS)
                order = CONDITIONS[rotation:] + CONDITIONS[:rotation]
                case_rows = []
                for mode, variant in order:
                    row = execute_agent(model, case, bank.load(trial, variant), seed + trial,
                        f"trial-{trial}/{mode}/{variant}/{case.id}", mode)
                    row.update({"phase": "transfer", "trial": trial, "mode": mode, "variant": variant, "ordinal": ordinal})
                    rollouts.append(row)
                    case_rows.append(row)
                    append(destination / "rollouts.jsonl", row)
                    progress(destination, {"status": "in_progress", "completed": len(rollouts), "total": total,
                        "trial": trial, "ordinal": ordinal, "model_calls": model.calls})
                print(f"Dataset {trial+1}/{trials}, task {ordinal+1}/9: {sum(row['grade']['passed'] for row in case_rows)}/6 complete; "
                    f"wrong commits={sum(row['grade']['wrong_write_commits'] for row in case_rows)}, "
                    f"blocked={sum(row['grade']['blocked_writes'] for row in case_rows)}; {len(rollouts)}/{total} rollouts", flush=True)
        if source_hashes() != protocol["source_hashes"]:
            raise ValueError("Frozen source changed during experiment")
        shared_tokens = {"input": sum(row["input_tokens"] for row in training), "output": sum(row["output_tokens"] for row in training)}
        calls = [json.loads(line) for line in (destination / "model-calls.jsonl").read_text(encoding="utf-8").splitlines()]
        proposal_ids = {proposal["call_id"] for proposal in proposals}
        for event in calls:
            if event["event"] == "response" and event["call_id"] in proposal_ids:
                shared_tokens["input"] += event["response"].get("prompt_eval_count", 0)
                shared_tokens["output"] += event["response"].get("eval_count", 0)
        report = {"version": "0.3.0", "status": "complete", "scope": "local real-agent 3×2 matched pilot; one affine connector task family",
            "protocol": protocol, "runtime": metadata, "results": summarize_execution(rollouts),
            "shared_learning": {"episodes": len(training), "proposals": len(proposals),
                "model_calls": sum(row["model_calls"] for row in training) + len(proposals),
                "input_tokens": shared_tokens["input"], "output_tokens": shared_tokens["output"],
                "allocation": "charged equally to each condition; physically collected once"},
            "qualification": {"accepted": sum(gate["accepted"] for gate in gates), "rejected": sum(not gate["accepted"] for gate in gates),
                "structurally_invalid": sum(not proposal["structurally_valid"] for proposal in proposals),
                "model_calls": 0, "cases_evaluated": sum(len(gate["rows"]) for gate in gates),
                "wall_seconds": round(sum(gate["wall_seconds"] for gate in gates), 9)},
            "reference": {"scope": "scripted deterministic solver, not LLM results", "successful": sum(row["grade"]["passed"] for row in reference),
                "total": len(reference), "model_calls": 0},
            "total_actual_model_calls": model.calls, "total_actual_tokens": model.tokens,
            "local_http_requests": model.calls + 3, "remote_network_requests": 0, "paid_api_calls": 0,
            "restart_verified": True, "wall_seconds": round(time.monotonic() - started, 6),
            "limitations": ["One local 4B model and an authored affine task family; no broad intelligence or superiority claim.",
                "Five fixture datasets are a limited pilot, not independent external replication." if trials == 5 else "Limited authored fixture datasets.",
                "Guard effects are engineering controls; they must not be attributed to memory or model learning.",
                "The exact arithmetic helper is shared by all conditions; its standalone effect versus v0.2 is not causally measured.",
                "v0.3 scores correct committed state after recovery; v0.2 penalized any extra write attempt. Scores are not directly comparable.",
                "Unsafe attempted writes and clean completion remain reported, so blocked mistakes are not hidden.",
                "External typed memory changes; model weights and the supplied affine functional form do not.",
                "Equal limits do not mean equal realized token, calibration, validation or timing costs.",
                "Replay verifies captured outputs and world grading, not regeneration of language-model outputs.",
                "Native Windows, rendered browser layout, hosted CI and other models remain unverified."]}
        (destination / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        from .execution_report import render_execution
        (destination / "report.html").write_text(render_execution(report, rollouts), encoding="utf-8")
        progress(destination, {"status": "complete", "completed": len(rollouts), "total": total, "model_calls": model.calls})
        manifest = {path.name: sha256(path.read_bytes()).hexdigest() for path in sorted(destination.iterdir()) if path.is_file()}
        (destination / "manifest.json").write_text(canonical(manifest), encoding="utf-8")
        return report
    except Exception as error:
        progress(destination, {"status": "incomplete", "completed": len(rollouts), "total": total,
            "error": str(error), "retry": False, "model_calls_started": model.calls})
        raise
    finally:
        bank.close()


def verify_execution(destination: Path) -> dict:
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    mandatory = {"protocol.json", "fixtures.json", "reference.json", "memory.sqlite3", "runtime.json",
        "model-calls.jsonl", "rollouts.jsonl", "proposals.jsonl", "report.json", "report.html", "progress.json"}
    if not mandatory <= set(manifest) or set(manifest) - mandatory - {"gates.jsonl"}:
        raise ValueError("Unexpected execution evidence inventory")
    for name, digest in manifest.items():
        if Path(name).name != name or sha256((destination / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Changed evidence: {name}")
    protocol = json.loads((destination / "protocol.json").read_text(encoding="utf-8"))
    report = json.loads((destination / "report.json").read_text(encoding="utf-8"))
    if source_hashes() != protocol["source_hashes"] or report["protocol"] != protocol:
        raise ValueError("Replay requires the original frozen protocol and source")
    if protocol["system"] != EXECUTION_SYSTEM or canonical(protocol["tools"]) != canonical(EXECUTION_TOOLS):
        raise ValueError("Agent tools or instructions differ")
    datasets = {str(trial): make_execution_splits(protocol["seed"] + trial) for trial in range(protocol["trials"])}
    frozen = {trial: {name: [asdict(case) for case in cases] for name, cases in splits.items()} for trial, splits in datasets.items()}
    if canonical(frozen) != (destination / "fixtures.json").read_text(encoding="utf-8"):
        raise ValueError("Frozen inputs or oracle labels differ from independent regeneration")
    reference = [{"trial": trial, **reference_solve(case)} for trial in range(protocol["trials"]) for case in datasets[str(trial)]["transfer"]]
    if canonical(reference) != (destination / "reference.json").read_text(encoding="utf-8"):
        raise ValueError("Deterministic reference replay differs")
    events = [json.loads(line) for line in (destination / "model-calls.jsonl").read_text(encoding="utf-8").splitlines()]
    requests = {event["call_id"]: event for event in events if event["event"] == "request"}
    responses = {event["call_id"]: event for event in events if event["event"] == "response"}
    if len(events) != 2 * len(requests) or set(requests) != set(responses) or set(requests) != set(range(1, len(requests) + 1)):
        raise ValueError("Duplicate, incomplete or failed model calls")
    if len(requests) != report["total_actual_model_calls"]:
        raise ValueError("Model-call total differs")
    tokens = {"input": sum(event["response"].get("prompt_eval_count", 0) for event in responses.values()),
              "output": sum(event["response"].get("eval_count", 0) for event in responses.values())}
    if tokens != report["total_actual_tokens"]:
        raise ValueError("Token totals differ from recorded runtime consumption")
    records = [json.loads(line) for line in (destination / "rollouts.jsonl").read_text(encoding="utf-8").splitlines()]
    rows = [row for row in records if row["phase"] == "transfer"]
    proposals = [json.loads(line) for line in (destination / "proposals.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(proposals) != 2 * protocol["trials"]:
        raise ValueError("Shared proposal stage is incomplete")
    for trial in range(protocol["trials"]):
        expected_cases = {case.id for case in datasets[str(trial)]["transfer"]}
        for mode, variant in CONDITIONS:
            cell = [row for row in rows if (row["trial"], row["mode"], row["variant"]) == (trial, mode, variant)]
            if len(cell) != len(expected_cases) or {row["case_id"] for row in cell} != expected_cases:
                raise ValueError("Matched cells have missing or duplicate tasks")
        training = [row for row in records if row["phase"] == "training" and row["trial"] == trial]
        if len(training) != 2 or {row["case_id"] for row in training} != {case.id for case in datasets[str(trial)]["training"]}:
            raise ValueError("Shared training is incomplete")
    if len(records) != protocol["trials"] * (2 + 9 * 6):
        raise ValueError("Unexpected extra rollout records")
    used_calls = [call_id for row in records for call_id in row["call_ids"]] + [item["call_id"] for item in proposals]
    if len(used_calls) != len(set(used_calls)) or set(used_calls) != set(requests):
        raise ValueError("Model call provenance is duplicated or unassigned")
    expected_memory, replay_gates = {}, []
    for trial in range(protocol["trials"]):
        expected_memory[trial] = {variant: [] for variant in VARIANTS}
        scoped_proposals = [item for item in proposals if item["trial"] == trial]
        if len(scoped_proposals) != 2 or {item["source"] for item in scoped_proposals} != {case.source for case in datasets[str(trial)]["training"]}:
            raise ValueError("Proposal scopes differ from training")
        for item in scoped_proposals:
            try:
                payload = json.loads(responses[item["call_id"]]["response"]["message"]["content"])
                if set(payload) != {"source", "revision", "scale", "offset"}:
                    raise ValueError("Unknown proposal field")
                rule = AffineRule(**payload)
                valid = (rule.source, rule.revision) == (item["source"], item["revision"])
            except (TypeError, ValueError):
                valid = False
            if valid != item["structurally_valid"]:
                raise ValueError("Stored proposal differs from model output")
            if not valid:
                continue
            if asdict(rule) != item["rule"]:
                raise ValueError("Stored coefficients differ from model output")
            retained = [(old, case) for old in expected_memory[trial]["validated_memory"]
                for case in datasets[str(trial)]["qualification"] if (old.source, old.revision) == (case.source, case.revision)]
            gate = qualify_rule(rule, datasets[str(trial)]["qualification"], retained)
            gate.update({"trial": trial, "rule": asdict(rule), "model_calls": 0})
            replay_gates.append(gate)
            expected_memory[trial]["unvalidated_memory"].append(rule)
            if gate["accepted"]:
                expected_memory[trial]["validated_memory"].append(rule)
    recorded_gates = [json.loads(line) for line in (destination / "gates.jsonl").read_text(encoding="utf-8").splitlines()] if (destination / "gates.jsonl").exists() else []
    if replay_gates != [{key: value for key, value in gate.items() if key != "wall_seconds"} for gate in recorded_gates]:
        raise ValueError("Qualification replay differs")
    bank = MemoryBank(destination / "memory.sqlite3", read_only=True)
    try:
        for trial in expected_memory:
            for variant in VARIANTS:
                if bank.load(trial, variant) != sorted(expected_memory[trial][variant], key=lambda rule: (rule.source, rule.revision)):
                    raise ValueError("Persisted memory differs from independently checked proposals")
        for row in records:
            case = next(case for case in datasets[str(row["trial"])][row["phase"]] if case.id == row["case_id"])
            memory = [] if row["phase"] == "training" else bank.load(row["trial"], row["variant"])
            captured = CapturedModel(row["call_ids"], requests, responses)
            replay = execute_agent(captured, case, memory, protocol["seed"] + row["trial"], "replay", row["mode"],
                protocol["max_calls_per_rollout"], protocol["max_tools_per_rollout"])
            if captured.ids or any(canonical(replay[field]) != canonical(row[field]) for field in SEMANTIC_FIELDS):
                raise ValueError(f"World and decision replay differs: {row['case_id']}")
    finally:
        bank.close()
    if summarize_execution(rows) != report["results"]:
        raise ValueError("Summary differs from actual per-case evidence")
    return {"model_rollouts_replayed": len(records), "transfer_rollouts": len(rows),
        "reference_controls_replayed": len(reference), "model_calls_verified": len(requests), "new_model_calls": 0,
        "new_remote_requests": 0}
