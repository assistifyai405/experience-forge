import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import tempfile

from .core import Skill, Store, canonical, evaluate, fingerprint, propose
from .fixtures import make_splits


def run_demo(destination: Path, seed: int) -> dict:
    # Fresh directory only: never overwrite an existing evidence run or database.
    destination.mkdir(parents=True, exist_ok=False)
    splits = make_splits(seed)
    destination.joinpath("fixtures.json").write_text(canonical({name: [asdict(case) for case in cases] for name, cases in splits.items()}), encoding="utf-8")
    # Training and transfer digests are committed before search; transfer is opened
    # for evaluation only after the active skill has been selected and persisted.
    store = Store(destination / "experience.sqlite3")
    try:
        store.record_experiences(splits["training"])
        baseline = Skill()
        proposals = propose(splits["training"])
        attempts = []
        for candidate in proposals:
            gate = store.attempt(candidate, splits["retention"], splits["qualification"])
            attempts.append(gate)
            if gate["accepted"]:
                break
        version, learned = store.active()
        journal = store.journal()
    finally:
        store.close()
    # Fresh connection: persisted skill must produce the same behavior after restart.
    reopened = Store(destination / "experience.sqlite3")
    try:
        restored_version, restored = reopened.active()
    finally:
        reopened.close()
    before = evaluate(baseline, splits["transfer"])
    after = evaluate(restored, splits["transfer"])
    improvement = after["correct"] - before["correct"]
    restored_ok = (version, learned) == (restored_version, restored)
    result = {
        "project": "Experience Forge", "version": "0.1.0", "seed": seed,
        "scope": "bounded program synthesis on synthetic number-format tasks; not an LLM evaluation",
        "model_calls": 0, "network_calls": 0, "model_weights_updated": False,
        "fixture_sha256": fingerprint({name: [asdict(case) for case in cases] for name, cases in splits.items()}),
        "proposals": [skill.feature for skill in proposals], "attempts": attempts,
        "active_version": restored_version, "learned_rule": restored.description,
        "training_before": evaluate(baseline, splits["training"]),
        "training_after": evaluate(restored, splits["training"]),
        "transfer_before": before, "transfer_after": after,
        "transfer_gain": improvement, "restart_verified": restored_ok,
        "demonstration_passed": version > 0 and improvement > 0 and restored_ok,
        "limitations": ["Fixed, authored hypothesis language and synthetic task distribution.",
                        "Qualification labels select rules; transfer labels do not.",
                        "No LLM, general intelligence, causal discovery or weight training demonstrated.",
                        "Observed regression absence does not guarantee safety on arbitrary future inputs.",
                        "No full CSV ingestion or production number parser."],
    }
    destination.joinpath("report.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    destination.joinpath("journal.json").write_text(json.dumps(journal, indent=2, ensure_ascii=False), encoding="utf-8")
    from .report import render
    destination.joinpath("report.html").write_text(render(result), encoding="utf-8")
    manifest = {path.name: sha256(path.read_bytes()).hexdigest() for path in sorted(destination.iterdir()) if path.is_file()}
    destination.joinpath("manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Local experience-to-skill demonstration; no API key or installation required.")
    parser.add_argument("command", choices=["demo", "verify", "agent-benchmark", "agent-verify", "execution-benchmark", "execution-verify", "reuse-benchmark", "reuse-verify"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--trials", type=int)
    parser.add_argument("--model", default="qwen3.5:4b")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    if args.seed is None:
        args.seed = 60701 if args.command in ("reuse-benchmark", "reuse-verify") else 42
    if args.trials is not None and not 1 <= args.trials <= 10:
        parser.error("--trials must be between 1 and 10")
    if args.command in ("reuse-benchmark", "reuse-verify"):
        from .reuse_benchmark import run_reuse_comparison, verify_reuse
        if args.output is None:
            parser.error("reuse commands require --output; new benchmark directories must not exist")
        if args.command == "reuse-verify":
            print(json.dumps(verify_reuse(args.output), indent=2))
        else:
            result = run_reuse_comparison(args.output, args.seed, args.trials or 5, args.model, args.endpoint)
            print(json.dumps(result["results"], indent=2))
        return
    if args.command in ("execution-benchmark", "execution-verify"):
        from .execution_benchmark import run_execution_comparison, verify_execution
        if args.command == "execution-verify":
            if args.output is None:
                parser.error("execution-verify requires --output RUN_DIRECTORY")
            print(json.dumps(verify_execution(args.output), indent=2))
            return
        if args.output is None:
            from datetime import datetime, timezone
            args.output = Path("runs") / ("execution-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ"))
        result = run_execution_comparison(args.output, args.seed, args.trials or 5, args.model, args.endpoint)
        print(json.dumps(result["results"], indent=2))
        print(f"Report: {args.output.resolve() / 'report.html'}")
        return
    if args.command in ("agent-benchmark", "agent-verify"):
        from .agent_benchmark import run_comparison, verify_comparison
        if args.command == "agent-verify":
            if args.output is None:
                parser.error("agent-verify requires --output RUN_DIRECTORY")
            print(json.dumps(verify_comparison(args.output), indent=2))
            return
        if args.output is None:
            from datetime import datetime, timezone
            args.output = Path("runs") / ("agent-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ"))
        result = run_comparison(args.output, args.seed, args.trials or 2, args.model, args.endpoint)
        print(json.dumps(result["results"], indent=2))
        print(f"Report: {args.output.resolve() / 'report.html'}")
        return
    if args.command == "verify":
        if args.output is None:
            parser.error("verify requires --output RUN_DIRECTORY")
        manifest = json.loads((args.output / "manifest.json").read_text(encoding="utf-8"))
        expected_names = {"experience.sqlite3", "fixtures.json", "journal.json", "report.json", "report.html"}
        if set(manifest) != expected_names:
            raise SystemExit("Invalid manifest file inventory")
        for name, digest in manifest.items():
            if sha256((args.output / name).read_bytes()).hexdigest() != digest:
                raise SystemExit(f"Artifact changed: {name}")
        original = json.loads((args.output / "report.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            replay = run_demo(Path(tmp) / "replay", original["seed"])
        if canonical(replay) != canonical(original):
            raise SystemExit("Independent deterministic replay differs")
        if not original["demonstration_passed"]:
            raise SystemExit("Evidence intact, but demonstration failed")
        print("Artifact hashes and independent deterministic replay verified.")
        return
    if args.output is None:
        from datetime import datetime, timezone
        args.output = Path("runs") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    result = run_demo(args.output, args.seed)
    print(f"Learned: {result['learned_rule']}")
    print(f"Transfer: {result['transfer_before']['correct']}/{result['transfer_before']['total']} -> {result['transfer_after']['correct']}/{result['transfer_after']['total']}")
    print(f"Restart verified: {result['restart_verified']}; model calls: 0; network calls: 0")
    print(f"Report: {args.output.resolve() / 'report.html'}")
    if not result["demonstration_passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
