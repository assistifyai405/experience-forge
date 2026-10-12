"""Three-treatment live comparison, explicit provenance, and model-free replay."""
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import random
import sqlite3
import time

from .connector_tasks import AffineRule, ConnectorCase, make_connector_splits, qualify_rule
from .core import canonical
from .local_agent import LocalModel, run_agent, propose_from_episodes, TOOLS

VARIANTS = ("no_memory", "unvalidated_memory", "validated_memory")
SEMANTIC_FIELDS = ("case_id", "public_input", "category", "memory", "grade", "finished", "stop", "final",
                   "tool_events", "call_ids", "model_calls", "tool_calls", "input_tokens", "output_tokens")


def append(path: Path, value: dict):
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical(value) + "\n")
        handle.flush()


class MemoryBank:
    def __init__(self, path: Path, read_only: bool = False):
        self.db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) if read_only else sqlite3.connect(path)
        if read_only:
            return
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS rules (trial INTEGER, variant TEXT, source TEXT, revision TEXT, payload TEXT,
                PRIMARY KEY(trial, variant, source, revision));
            CREATE TABLE IF NOT EXISTS decisions (id INTEGER PRIMARY KEY, trial INTEGER, proposal TEXT, gate TEXT);
        """)

    def save(self, trial: int, rule: AffineRule, gate: dict):
        with self.db:
            self.db.execute("INSERT INTO decisions(trial,proposal,gate) VALUES (?,?,?)", (trial, canonical(asdict(rule)), canonical(gate)))
            for variant in ("unvalidated_memory", "validated_memory"):
                if variant == "validated_memory" and not gate["accepted"]:
                    continue
                self.db.execute("INSERT OR REPLACE INTO rules VALUES (?,?,?,?,?)",
                    (trial, variant, rule.source, rule.revision, canonical(asdict(rule))))

    def load(self, trial: int, variant: str) -> list[AffineRule]:
        if variant not in VARIANTS:
            raise ValueError("Unknown memory treatment")
        return [AffineRule(**json.loads(row[0])) for row in self.db.execute(
            "SELECT payload FROM rules WHERE trial=? AND variant=? ORDER BY source,revision", (trial, variant))]

    def close(self):
        self.db.close()


def summarize(rollouts: list[dict]) -> dict:
    summary = {}
    for variant in VARIANTS:
        rows = [row for row in rollouts if row["variant"] == variant]
        successes = sum(row["grade"]["passed"] for row in rows)
        summary[variant] = {"successful": successes, "total": len(rows),
            "model_calls": sum(row["model_calls"] for row in rows),
            "tool_calls": sum(row["tool_calls"] for row in rows),
            "input_tokens": sum(row["input_tokens"] for row in rows),
            "output_tokens": sum(row["output_tokens"] for row in rows),
            "calibration_reads": sum(row["grade"]["calibration_reads"] for row in rows),
            "wall_seconds": round(sum(row["wall_seconds"] for row in rows), 6),
            "per_trial": [{"trial": trial, "successful": sum(row["grade"]["passed"] for row in rows if row["trial"] == trial),
                "total": sum(row["trial"] == trial for row in rows)} for trial in sorted({row["trial"] for row in rows})]}
    pairs = {}
    for variant in VARIANTS[1:]:
        wins, losses, equal = 0, 0, 0
        for row in (row for row in rollouts if row["variant"] == variant):
            baseline = next(item for item in rollouts if item["variant"] == "no_memory" and (item["trial"], item["case_id"]) == (row["trial"], row["case_id"]))
            delta = int(row["grade"]["passed"]) - int(baseline["grade"]["passed"])
            wins += delta > 0
            losses += delta < 0
            equal += delta == 0
        pairs[variant] = {"wins": wins, "losses": losses, "ties": equal}
    return {"variants": summary, "paired_vs_no_memory": pairs}


def source_hashes() -> dict:
    root = Path(__file__).parent
    return {path.name: sha256(path.read_bytes()).hexdigest() for path in sorted(root.glob("*.py"))}


def run_comparison(destination: Path, seed: int = 31415, trials: int = 2, model_name: str = "qwen3.5:4b",
                   endpoint: str = "http://127.0.0.1:11434", max_calls: int = 6, max_tools: int = 8) -> dict:
    if not 1 <= trials <= 10 or not 1 <= max_calls <= 12 or not 1 <= max_tools <= 16:
        raise ValueError("Invalid bounded benchmark configuration")
    destination.mkdir(parents=True, exist_ok=False)
    config = {"seed": seed, "trials": trials, "model": model_name, "endpoint": endpoint,
        "max_calls_per_rollout": max_calls, "max_tools_per_rollout": max_tools,
        "max_output_tokens_per_call": 256, "temperature": 0, "num_ctx": 8192,
        "variants": list(VARIANTS), "variant_order": "balanced rotation; seeded case shuffle",
        "learning": "shared training episodes and shared model-generated typed affine proposals",
        "selection": "only validated memory uses deterministic qualification results",
        "final_labels": "never supplied to agent or proposer; accessed for grading after rollout",
        "budget": "same model and per-rollout call/tool/token ceilings; realized costs reported, not claimed equal",
        "paid_api_allowed": False, "source_hashes": source_hashes()}
    datasets = {str(trial): make_connector_splits(seed + trial) for trial in range(trials)}
    frozen = {trial: {name: [asdict(case) for case in cases] for name, cases in splits.items()} for trial, splits in datasets.items()}
    # Protocol and all partitions are frozen before the first benchmark model call.
    (destination / "protocol.json").write_text(canonical(config), encoding="utf-8")
    (destination / "fixtures.json").write_text(canonical(frozen), encoding="utf-8")
    model = LocalModel(destination, model_name, endpoint, max_calls=trials * (2 * max_calls + 2 + 8 * 3 * max_calls))
    results, proposals, training, gates = [], [], [], []
    bank = MemoryBank(destination / "memory.sqlite3")
    start = time.monotonic()
    try:
        metadata = model.preflight()
        (destination / "runtime.json").write_text(canonical(metadata), encoding="utf-8")
        for trial in range(trials):
            splits = datasets[str(trial)]
            for case in splits["training"]:
                rollout = run_agent(model, case, [], seed + trial, f"trial-{trial}/training/{case.id}", max_calls, max_tools)
                rollout.update({"trial": trial, "phase": "training", "variant": "shared"})
                append(destination / "rollouts.jsonl", rollout)
                training.append(rollout)
                print(f"Trial {trial+1}/{trials}: shared training {case.source}, success={rollout['grade']['passed']}", flush=True)
            for case in splits["training"]:
                episodes = [row for row in training if row["trial"] == trial and row["public_input"]["source"] == case.source]
                rule, proposal = propose_from_episodes(model, episodes, seed + trial, f"trial-{trial}/proposal/{case.source}")
                proposal.update({"trial": trial, "source": case.source, "revision": case.revision})
                if rule is not None and (rule.source, rule.revision) != (case.source, case.revision):
                    proposal["structurally_valid"] = False
                    proposal["error"] = "Proposed scope does not match training source/revision"
                    rule = None
                proposals.append(proposal)
                append(destination / "proposals.jsonl", proposal)
                if rule is not None:
                    current = bank.load(trial, "validated_memory")
                    retained = [(old, item) for old in current for item in splits["qualification"]
                        if (old.source, old.revision) == (item.source, item.revision)]
                    gate = qualify_rule(rule, splits["qualification"], retained)
                    gate.update({"trial": trial, "rule": asdict(rule), "model_calls": 0})
                    gates.append(gate)
                    append(destination / "gates.jsonl", gate)
                    bank.save(trial, rule, gate)
                    print(f"  Generated rule {rule.source}: scale={rule.scale}, offset={rule.offset}, accepted={gate['accepted']}", flush=True)
            snapshot = {variant: [asdict(rule) for rule in bank.load(trial, variant)] for variant in VARIANTS}
            bank.close()
            bank = MemoryBank(destination / "memory.sqlite3")
            if snapshot != {variant: [asdict(rule) for rule in bank.load(trial, variant)] for variant in VARIANTS}:
                raise RuntimeError("Memory changed after reopening SQLite")
            cases = list(splits["transfer"])
            random.Random(seed + trial).shuffle(cases)
            for ordinal, case in enumerate(cases):
                rotation = (trial + ordinal) % len(VARIANTS)
                order = VARIANTS[rotation:] + VARIANTS[:rotation]
                for variant in order:
                    memory = bank.load(trial, variant)
                    rollout = run_agent(model, case, memory, seed + trial, f"trial-{trial}/{variant}/{case.id}", max_calls, max_tools)
                    rollout.update({"trial": trial, "phase": "transfer", "variant": variant, "ordinal": ordinal})
                    results.append(rollout)
                    append(destination / "rollouts.jsonl", rollout)
                    print(f"Trial {trial+1}/{trials}, task {ordinal+1}/{len(cases)}, {variant}: success={rollout['grade']['passed']}, calls={rollout['model_calls']}", flush=True)
        if source_hashes() != config["source_hashes"]:
            raise RuntimeError("Agent source changed during the frozen experiment")
        paired = summarize(results)
        shared_tokens = {"input": sum(row["input_tokens"] for row in training), "output": sum(row["output_tokens"] for row in training)}
        proposal_calls = {item["call_id"] for item in proposals}
        for line in (destination / "model-calls.jsonl").read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event["event"] == "response" and event["call_id"] in proposal_calls:
                shared_tokens["input"] += event["response"].get("prompt_eval_count", 0)
                shared_tokens["output"] += event["response"].get("eval_count", 0)
        report = {"version": "0.2.0", "status": "complete", "scope": "actual local LLM tool-agent pilot on one synthetic affine connector family",
            "protocol": config, "runtime": metadata, "results": paired,
            "shared_learning": {"episodes": len(training), "proposals": len(proposals),
                "model_calls": sum(row["model_calls"] for row in training) + len(proposals),
                "input_tokens": shared_tokens["input"], "output_tokens": shared_tokens["output"],
                "cost_allocation": "charged equally to each treatment for controlled comparison; physically collected once"},
            "qualification": {"accepted": sum(gate["accepted"] for gate in gates), "rejected": sum(not gate["accepted"] for gate in gates),
                "model_calls": 0, "cases_evaluated": sum(len(gate["rows"]) for gate in gates),
                "cost_note": "extra deterministic qualification work belongs only to validated memory in deployment"},
            "total_actual_model_calls": model.calls, "total_actual_tokens": model.tokens,
            "local_http_requests": model.calls + 3, "remote_network_requests": 0, "paid_api_calls": 0,
            "restart_verified": True, "wall_seconds": round(time.monotonic() - start, 6),
            "limitations": ["One small authored affine task family and one local 4B model; no broad intelligence claim.",
                "Two trials are a pilot, not a statistically powered benchmark." if trials == 2 else "Limited pilot; inspect trial count before interpreting results.",
                "Shared training is collected without memory, so this isolates reuse/validation rather than independent online curricula.",
                "Learning modifies external typed skills, never model weights. The affine form is supplied in advance.",
                "Qualification evaluates typed rules, not arbitrary programs or all future agent behavior.",
                "Native Windows, other models and hosted CI are not established by this run.",
                "Same execution ceilings do not imply identical realized tokens or wall time; order and cache effects remain possible.",
                "Model-free replay verifies captured decisions and state grading; it does not regenerate model outputs."]}
        (destination / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        from .agent_report import render_comparison
        (destination / "report.html").write_text(render_comparison(report, results, gates), encoding="utf-8")
        files = {path.name: sha256(path.read_bytes()).hexdigest() for path in sorted(destination.iterdir()) if path.is_file()}
        (destination / "manifest.json").write_text(canonical(files), encoding="utf-8")
        return report
    except Exception as error:
        (destination / "interrupted.json").write_text(canonical({"status": "incomplete", "error": str(error),
            "model_calls_started": model.calls, "automatic_retry": False}), encoding="utf-8")
        raise
    finally:
        bank.close()


class CapturedModel:
    """Feed original model outputs to the real tool loop without calling a model."""
    def __init__(self, calls: list[int], requests: dict, responses: dict):
        self.ids = list(calls)
        self.requests, self.responses = requests, responses
        self.calls = calls[0] - 1
        self.tokens = {"input": 0, "output": 0}

    def chat(self, messages, seed, tag, *, tools=False, schema=None, tool_definitions=None):
        if not self.ids:
            raise ValueError("Replay consumed unexpected extra model call")
        call_id = self.ids.pop(0)
        body = self.requests[call_id]["body"]
        if canonical(messages) != canonical(body["messages"]) or seed != body["options"]["seed"]:
            raise ValueError("Replay prompt differs from original model request")
        expected_tools = TOOLS if tool_definitions is None else tool_definitions
        if tools and canonical(body.get("tools")) != canonical(expected_tools):
            raise ValueError("Replay tools differ from original model request")
        response = self.responses[call_id]["response"]
        self.calls = call_id
        self.tokens["input"] += response.get("prompt_eval_count", 0)
        self.tokens["output"] += response.get("eval_count", 0)
        return response


def verify_comparison(destination: Path) -> dict:
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    mandatory = {"protocol.json", "fixtures.json", "runtime.json", "memory.sqlite3", "rollouts.jsonl",
                 "proposals.jsonl", "model-calls.jsonl", "report.json", "report.html"}
    if not mandatory <= set(manifest) or set(manifest) - mandatory - {"gates.jsonl"}:
        raise ValueError("Unexpected evidence inventory")
    for name, digest in manifest.items():
        if Path(name).name != name or sha256((destination / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Changed evidence: {name}")
    report = json.loads((destination / "report.json").read_text(encoding="utf-8"))
    protocol = json.loads((destination / "protocol.json").read_text(encoding="utf-8"))
    if report["protocol"] != protocol:
        raise ValueError("Report protocol differs")
    if source_hashes() != protocol["source_hashes"]:
        raise ValueError("Replay requires the source version used for this run")
    datasets = {str(trial): make_connector_splits(protocol["seed"] + trial) for trial in range(protocol["trials"])}
    regenerated = {trial: {name: [asdict(case) for case in cases] for name, cases in splits.items()} for trial, splits in datasets.items()}
    if canonical(regenerated) != (destination / "fixtures.json").read_text(encoding="utf-8"):
        raise ValueError("Frozen fixtures differ from independently regenerated labels")
    events = [json.loads(line) for line in (destination / "model-calls.jsonl").read_text(encoding="utf-8").splitlines()]
    requests = {event["call_id"]: event for event in events if event["event"] == "request"}
    responses = {event["call_id"]: event for event in events if event["event"] == "response"}
    if len(requests) != len(responses) or set(requests) != set(responses) or len(requests) != report["total_actual_model_calls"]:
        raise ValueError("Model calls are incomplete or count differs")
    if len(events) != 2 * len(requests) or set(requests) != set(range(1, len(requests) + 1)):
        raise ValueError("Duplicate or missing model request/response events")
    tokens = {"input": sum(event["response"].get("prompt_eval_count", 0) for event in responses.values()),
              "output": sum(event["response"].get("eval_count", 0) for event in responses.values())}
    if tokens != report["total_actual_tokens"]:
        raise ValueError("Reported token consumption differs from model evidence")
    records = [json.loads(line) for line in (destination / "rollouts.jsonl").read_text(encoding="utf-8").splitlines()]
    transfer = [row for row in records if row["phase"] == "transfer"]
    for trial in range(protocol["trials"]):
        expected = {case.id for case in datasets[str(trial)]["transfer"]}
        for variant in VARIANTS:
            rows = [row for row in transfer if row["trial"] == trial and row["variant"] == variant]
            if len(rows) != len(expected) or {row["case_id"] for row in rows} != expected:
                raise ValueError("Unbalanced or duplicated comparison")
    proposals = [json.loads(line) for line in (destination / "proposals.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(proposals) != protocol["trials"] * 2:
        raise ValueError("Incomplete shared proposal stage")
    regenerated_gates, expected_memory = [], {}
    for trial in range(protocol["trials"]):
        expected_memory[trial] = {variant: [] for variant in VARIANTS}
        expected_sources = {case.source for case in datasets[str(trial)]["training"]}
        trial_proposals = [item for item in proposals if item["trial"] == trial]
        if len(trial_proposals) != 2 or {item["source"] for item in trial_proposals} != expected_sources:
            raise ValueError("Proposal sources differ from training")
        for item in trial_proposals:
            content = responses[item["call_id"]]["response"]["message"]["content"]
            try:
                payload = json.loads(content)
                if set(payload) != {"source", "revision", "scale", "offset"}:
                    raise ValueError("Invalid proposal fields")
                rule = AffineRule(**payload)
                valid = (rule.source, rule.revision) == (item["source"], item["revision"])
            except (TypeError, ValueError):
                valid = False
            if valid != item["structurally_valid"]:
                raise ValueError("Proposal validity differs from captured model output")
            if not valid:
                continue
            if asdict(rule) != item["rule"]:
                raise ValueError("Stored rule differs from actual model proposal")
            retained = [(old, case) for old in expected_memory[trial]["validated_memory"]
                        for case in datasets[str(trial)]["qualification"]
                        if (old.source, old.revision) == (case.source, case.revision)]
            gate = qualify_rule(rule, datasets[str(trial)]["qualification"], retained)
            gate.update({"trial": trial, "rule": asdict(rule), "model_calls": 0})
            regenerated_gates.append(gate)
            expected_memory[trial]["unvalidated_memory"].append(rule)
            if gate["accepted"]:
                expected_memory[trial]["validated_memory"].append(rule)
    recorded_gates = [json.loads(line) for line in (destination / "gates.jsonl").read_text(encoding="utf-8").splitlines()] if (destination / "gates.jsonl").exists() else []
    if regenerated_gates != recorded_gates:
        raise ValueError("Qualification decisions differ from independent evaluation")
    bank = MemoryBank(destination / "memory.sqlite3", read_only=True)
    try:
        for trial in expected_memory:
            for variant in VARIANTS:
                expected = sorted(expected_memory[trial][variant], key=lambda rule: (rule.source, rule.revision))
                if bank.load(trial, variant) != expected:
                    raise ValueError("Persisted memories differ from proposal/qualification evidence")
        for row in records:
            case = next(case for case in datasets[str(row["trial"])][row["phase"]] if case.id == row["case_id"])
            memory = [] if row["phase"] == "training" else bank.load(row["trial"], row["variant"])
            captured = CapturedModel(row["call_ids"], requests, responses)
            replay = run_agent(captured, case, memory, protocol["seed"] + row["trial"], "replay",
                protocol["max_calls_per_rollout"], protocol["max_tools_per_rollout"])
            if captured.ids or any(canonical(replay[field]) != canonical(row[field]) for field in SEMANTIC_FIELDS):
                raise ValueError(f"State/decision replay differs: {row['case_id']}")
    finally:
        bank.close()
    if summarize(transfer) != report["results"]:
        raise ValueError("Summary differs from per-case evidence")
    return {"rollouts_replayed": len(records), "transfer_rollouts": len(transfer), "model_calls_verified": len(requests),
            "new_model_calls": 0, "remote_requests": 0}
