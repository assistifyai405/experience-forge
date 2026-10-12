# Execution milestone 0.3 — 12 October 2026

**Delivered:** exact arithmetic, evidence-bound writes, a matched six-condition comparison, and replayable evidence. **Measured:** all six conditions completed 45/45 tasks with zero wrong commits and zero unsafe write attempts. This run demonstrates correct execution in the authored family; it does **not** demonstrate a memory advantage or an incremental live benefit of write enforcement.

Complete run: `runs/execution-milestone-20261012-complete/`, fixture seeds **60606–60610**. Annotated viewer: `reports/execution-milestone-20261012.html`. The frozen original viewer and raw data remain unchanged in the evidence folder.

## Matched live results

| Write control | Memory | Correct completion | Clean completion | Wrong commits | Unsafe attempts | Blocked writes | Transfer inference calls |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Off | None | 45/45 | 45/45 | 0 | 0 | 0 | 195 |
| Off | Unvalidated | 45/45 | 45/45 | 0 | 0 | 0 | 196 |
| Off | Validated | 45/45 | 45/45 | 0 | 0 | 0 | 196 |
| On | None | 45/45 | 45/45 | 0 | 0 | 0 | 195 |
| On | Unvalidated | 45/45 | 45/45 | 0 | 0 | 0 | 196 |
| On | Validated | 45/45 | 45/45 | 0 | 0 | 0 | 196 |

Every condition completed 9/9 cases in each of five datasets. All 270 final rollouts are retained. There is no required winner and no significance claim. All paired completion effects and wrong-commit reductions were zero.

The deterministic reference solver also passed **45/45**, making **zero model calls**. It is a scripted control, excluded from live model scores.

## What the agent actually did

All ten model-generated proposals passed independent qualification on twenty numeric examples. The external memories survived database reopen. Yet the agent invoked `derive_calibration_rule` in **45/45 final cases under every condition**, including those with matching remembered rules. Memory therefore did not replace calibration lookups or reduce inference calls. We cannot infer hidden internal use of memory from this alone.

The report field `exact_derivations` counts **helper invocations**, including missing-input and conflicting-data attempts. It is not a count of successful fits. Each condition had 35 supported numeric cases and 10 required abstentions; the annotated viewer labels this column as helper calls to make that distinction explicit.

This is a ceiling effect in a small task family solvable by the supplied exact helper. The outcome supports the helper/tool-loop implementation's correctness on these fixtures, but it cannot establish the helper's standalone causal effect against v0.2: the dataset, tools and scoring contract changed. No direct before/after score claim is made.

## Costs and limits

| Condition | Transfer input tokens | Transfer output tokens | Transfer tool calls | Transfer wall time |
| --- | ---: | ---: | ---: | ---: |
| Control off / none | 175,948 | 5,511 | 150 | 87.60 s |
| Control off / unvalidated | 181,254 | 5,881 | 151 | 92.39 s |
| Control off / validated | 181,254 | 5,881 | 151 | 87.85 s |
| Control on / none | 175,948 | 5,511 | 150 | 87.95 s |
| Control on / unvalidated | 181,254 | 5,881 | 151 | 92.39 s |
| Control on / validated | 181,254 | 5,881 | 151 | 87.03 s |

Shared learning: **60 inference calls**, **51,003 input tokens**, **1,867 output tokens**, consisting of ten common training episodes and ten actual model proposal calls. This phase was physically collected once and charged equally to all six conditions. Add it once to a condition's transfer consumption when estimating that condition's controlled-study cost; do not sum those assigned costs as physical traffic.

Complete run physical consumption: **1,234 actual local inference calls**, **1,127,915 input tokens**, **36,413 output tokens**, **573.22 seconds** elapsed. Qualification used **zero model calls** and approximately 0.000286 s of measured local deterministic checking, excluding broader database and orchestration work. Write-control and arithmetic CPU work are included in per-rollout wall times.

Model: `qwen3.5:4b` (4.7B, Q4_K_M), digest `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`, Ollama 0.33.3, Python 3.14.4 on the local Linux/WSL execution host. Thinking disabled, temperature zero, context 8192, maximum 256 generated tokens per call, 8 calls and 12 tools per rollout. No model weights were updated.

**No paid API calls or external provider requests occurred.** Timing differences are descriptive; they are not evidence of faster memory or statistically superior execution.

## Preserved infrastructure failure and its cost

The first suite, seeds 60601–60605, lost its disposable execution session after 64 completed final rollouts. Its process no longer existed. The log recorded **292 started requests, 291 responses**, with request 292 unanswered in the evidence. It was not retried. Those original case IDs were not reissued.

The incomplete folder remains under `runs/execution-milestone-20261012/`, with an interruption audit and file hashes. All **68 completed model-driven rollouts** in that prefix, including four training episodes, were independently replayed. It is not a balanced completed comparison and is excluded from final performance scores, but **not from work/cost accounting**. Its recorded responses consumed **265,358 input tokens and 9,107 output tokens**; consumption for the unanswered request is unknown, not assumed zero.

A separate five-call development smoke test used training seed 90909. Its evidence is also retained separately. Neither the smoke nor the incomplete prefix is represented as part of the complete 270-rollout comparison. The complete replacement suite used mechanically selected new seeds and identical Python source, prompts, budgets and scoring. There was no tuning based on its final labels.

## Verification and interpretation

**40 unit/contract tests passed.** They check rational arithmetic, conflicting/insufficient observations, hidden-label independence, wrong guesses, mismatched values, stale proof invalidation, changed source/revision/input/calibration, duplicate writes, recovery, missing input, endpoint rejection, balanced comparison and model-free replay. Scripted test controls are separate from actual model results.

Full evidence verification regenerated labels, rechecked proposals and qualification, reloaded memories, replayed **280 actual model-driven rollouts**, repeated **45 deterministic reference controls**, and validated **1,234 captured inference calls**. It made no new model or remote requests.

```bash
python3 -m experience_forge execution-verify --output runs/execution-milestone-20261012-complete
```

In the release archive, use `--output evidence/execution-complete` instead. Older v0.2 source and evidence are preserved under `history/v0.2.0/experience-forge`; that version's 52 rollouts and 232 calls were reverified before changes.

The write checks do block bad attempts in targeted tests, including ones whose guessed value accidentally matches the hidden expected quantity. They use available calibration and computation evidence, not the grader's expected label. **No unsafe attempt occurred in the complete live run**, so no incremental guard benefit can be measured there.

The next informative study should require reuse of earlier experience when fresh calibration is unavailable, and include realistic distribution changes or inaccurate proposals. It should keep deterministic execution protection separate from learning effects, freeze new tasks before tuning, and preserve this ceiling result as evidence. Native Windows execution, rendered browser layout, hosted CI, other models and independent external replication remain unverified.
