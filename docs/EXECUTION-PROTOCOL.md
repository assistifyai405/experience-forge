# Frozen execution-control study — version 0.3

## Question

Can an evidence-bound write check reduce incorrect committed values, and what does external memory contribute separately? The study measures both. A blocked mistake is an engineering control, not evidence that a model has learned better.

## Matched six-condition design

Each case runs under all combinations of:

- no memory, unvalidated model-generated memory, independently qualified model-generated memory;
- extra write control off or on.

Every condition uses the same exact arithmetic helper, model, prompt, tools, memory representation and per-case budgets. The write-control mode is not named in the agent's prompt. It affects enforcement at the save tool only. Basic checks for integer bounds, missing input and duplicate commits remain active in both modes.

The helper derives `scale` and `offset` using exact `Fraction` arithmetic from available calibration observations and checks every observation for agreement. It never consults the hidden expected label. It is available in all six conditions, so this experiment does not isolate its standalone effect compared with the old v0.2 run.

With extra control on, a write needs the latest supported normalization. Its proof binds source, revision, raw input, calibration digest and resulting quantity. A failed or inconsistent new normalization invalidates an earlier proof. A rejected write does not consume the single permitted commit; the agent can recover with a correct supported computation. All unsafe attempts, including blocked attempts, remain recorded.

## Frozen suite and execution budget

The complete recorded suite uses **five fixture seeds: 60606–60610**, fixed before its first inference request. The initially planned 60601–60605 suite was interrupted by loss of its execution session; its complete logs remain preserved as an incomplete run. Each dataset includes two training episodes, four independent qualification examples and nine final cases: six new values for known contracts, one unseen revision, one missing input and one inconsistent calibration. Opaque task IDs and neutral revision identifiers prevent case names from leaking required abstention or partition labels into the prompt.

This gives **45 final tasks per condition, 270 actual final agent rollouts**, plus ten shared training episodes and ten model proposal calls. The agent receives no final expected labels. Final labels are used only by the independent state grader. The author knows the generator, so this remains a small authored pilot, not an independent external benchmark.

Each rollout has fresh messages and an isolated SQLite world. Conditions use the same trial seed and maximum **8 inference calls**, **12 tool actions**, **256 generated tokens per call**, **8192 context tokens**, temperature zero and thinking disabled. Case order is seeded-shuffled, and the six-condition order rotates per case. Order/cache effects can remain; actual consumption and timing are reported.

Shared training uses no memory and no extra write control, with the common arithmetic helper available. Its observed episodes and actual model-generated typed proposals are shared identically across all six conditions. The shared phase is physically executed once and charged equally to each condition in the controlled comparison. This tests reuse and filtering after common experience, not independent online learning curricula. Qualification consumes zero inference calls but adds CPU work to validated memory.

Protocol, complete fixture partitions, tools, instructions and Python source hashes are written before the first final experiment inference request. Source drift aborts the run. Failures remain in the denominator. A transport error stops as incomplete without retries or automatic resume.

## Primary and secondary outcomes

- **Wrong committed writes:** number of actual stored values differing from the independent expected state, including a write when the correct action was abstention.
- **Correct completion:** a completed model turn with correct actual state, exactly one successful commit and correct readback; required abstention needs an empty saved state.
- **Clean completion:** correct completion with zero unsafe write attempts.
- **Unsafe attempts and blocked writes:** counted separately, so controls cannot conceal model mistakes.
- Actual inference calls, input/output tokens, tool actions, calibration reads/checks, exact derivations and elapsed time.

Matched comparisons report memory effects within each write mode, and write-control effects within each memory treatment. A deterministic reference solver using the same available calibration and tools runs separately with zero model calls. Its results demonstrate the authored task's solvability, not language-model performance.

Version 0.2's completion score penalized any extra write attempt. Version 0.3 separately distinguishes blocked attempts from committed state and allows recovery. Therefore the two versions' completion scores are **not directly comparable**. The new six conditions all use the same new scoring contract.

## Development and preserved evidence

A development smoke test uses only a training example from seed 90909, separate from final seeds. Contract tests cover wrong guesses, stale proofs, changed source/revision/input/calibration, contradictory data, missing input, exact arithmetic, recovery and model-free replay. Scripted test controls are never included in live model scores.

The original v0.2 source and all evidence are preserved in `Experience-Forge-0.2.0-real-agent-source-and-evidence.zip` and an extracted snapshot under `../releases/v0.2.0/experience-forge`. Its 52 recorded rollouts and 232 captured model calls were reverified before changing the current source. Verify old runs with their matching archived source version.

Model-free verification of the new run regenerates all oracle labels, validates proposals and qualification, reloads memory, replays actual recorded model outputs through the exact tool implementation, recomputes outcomes and checks the deterministic reference. It does not regenerate model outputs or claim model determinism.

No paid calls, model downloads, software installations, GitHub publication or remote provider requests are part of this milestone.

## Infrastructure interruption

The first execution session disappeared after 64 completed transfer rollouts. No matching process remained. Its model log contained 292 started requests and 291 recorded responses; request 292 had no recorded answer. That request and the unfinished case were not retried. The old folder was marked incomplete with an interruption audit, without rewriting its fixtures, model logs or recorded rollouts.

A new complete suite uses the next five integer seeds, 60606–60610, with **identical source, prompts, scoring and budgets**. Selection of these seeds was mechanical, not based on which conditions won; no new test labels were inspected to choose them. The new process was launched independently of the disposable terminal session. The incomplete suite is reported separately and must not be silently folded into balanced final scores or discarded from cost accounting.
