# Experience reuse results — version 0.4, 12 October 2026

**Delivered:** a genuine local agent with explicit durable-memory retrieval, isolated task state, version/evidence checks, a frozen three-treatment outage pilot, full raw evidence and model-free replay.

**Measured:** no-memory completed 29/60 tasks; unvalidated and validated memory each completed 41/60. Both memory conditions demonstrated evidence-consistent reuse in 21/30 outage opportunities, with 13/30 fully committed and read back. Validation did not improve final completion. No wrong commits or unsafe write attempts occurred. These are small authored-pilot results, not proof of general intelligence.

Complete evidence: `runs/reuse-milestone-20261012/`. Portable package path: `evidence/reuse-complete/`. [Derived viewer](../reports/reuse-viewer/index.html), [frozen protocol](REUSE-PROTOCOL.md). The original report and data remain immutable.

## Matched outcomes

| Treatment | All tasks | Item retrieved | Historical use attempted | Supported reuse | Correct import + readback | Wrong commits | Failed normalizations |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No memory | 29/60 | 0/30 | 0/30 | 0/30 | 0/30 | 0 | 0 |
| Unvalidated memory | 41/60 | 27/30 | 24/30 | 21/30 | 13/30 | 0 | 20 |
| Validated memory | 41/60 | 27/30 | 24/30 | 21/30 | 13/30 | 0 | 18 |

The four memory proportions use only known-contract outage tasks. Failed normalizations and wrong commits count all final tasks. Retrieving a rule, applying it with evidence, and verifying its committed state are distinct outcomes.

| Task category | No memory | Unvalidated | Validated |
| --- | ---: | ---: | ---: |
| changed-version | 5/5 | 5/5 | 5/5 |
| conflict | 5/5 | 5/5 | 5/5 |
| known-outage | 0/30 | 13/30 | 13/30 |
| missing-input | 5/5 | 5/5 | 5/5 |
| online-control | 9/10 | 8/10 | 8/10 |
| unknown-contract | 5/5 | 5/5 | 5/5 |

All conditions correctly abstained in all 20 changed/unknown-version, missing-input and conflicting-evidence cases. No-memory lacked historical observations on all 30 known-contract outage tasks; it abstained there rather than guessing. Those tasks remain failures to complete the desired import, while unsupported abstention is separately reported. This information difference is intrinsic to the experiment.

## What still failed

In each memory condition, eight of the 21 evidence-consistent outage normalizations led to the correct stored value but the agent ended without calling the required readback tool. These eight are not counted as completed tasks. A final textual claim of verification is not a database read. The failure evidence was retained; no prompts were tuned or cases rerun to fix the score.

Both memory conditions also produced 15 normalization errors because the supplied memory ID did not refer to a retrieved item. One recorded example truncated `memory-5b34a978cea0c4da` to `memory-5b34a978cea0c4`. The environment rejected it instead of guessing which memory was intended. Failed use can recover, and every error stays logged.

Unvalidated memory additionally made two conflicting-evidence normalization attempts. Filtering removed these attempts but did not change final task completion; the shared exact-evidence control already prevented unsupported values from committing. This is a small observed error-attempt reduction, not proof of better general model behavior or lower future cost.

Qualification accepted **9** candidates, rejected **2**, and **4** proposals failed shape/domain/scope requirements before storage. The two rejections involved inconsistent contracts; the accepted regular candidates were shared unchanged. All 15 proposals were actual model outputs, not supplied coefficients. Qualification checked 18 numeric cases and used zero model calls.

## Seed-level comparison

| Seed | No memory | Unvalidated | Validated | Supported outage reuse in either memory |
| --- | ---: | ---: | ---: | ---: |
| 60701 | 6/12 | 7/12 | 7/12 | 4/6 |
| 60702 | 6/12 | 9/12 | 9/12 | 3/6 |
| 60703 | 5/12 | 9/12 | 9/12 | 6/6 |
| 60704 | 6/12 | 8/12 | 8/12 | 5/6 |
| 60705 | 6/12 | 8/12 | 8/12 | 3/6 |

Each memory comparison versus no-memory had 14 matched wins, 2 losses and 44 ties. Mean seed completion difference was +20 percentage points, with seed differences from +8.33 to +33.33 points and sample SD 9.50 points. There are five independent authored seeds, not 60 independent replications per treatment. This variation is descriptive, not a confidence bound or superiority claim.

## Actual consumption

| Treatment final phase | Inference calls | Input tokens | Output tokens | Tool actions | Elapsed seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| No memory | 201 | 198,868 | 10,283 | 141 | 141.73 |
| Unvalidated memory | 239 | 294,563 | 16,334 | 179 | 219.75 |
| Validated memory | 238 | 291,821 | 16,066 | 178 | 215.82 |

Shared learning: **85 actual local calls**, **80,751 input tokens**, **4,557 output tokens**, including 15 training episodes and 15 proposal requests. It was physically collected once and charged equally to every condition; add it once to a condition's final-phase cost, not three times to physical traffic.

Complete benchmark physical total: **763 local inference calls**, **866,003 input tokens**, **47,240 output tokens**, **646.76 seconds**. Qualification's measured CPU checking time was 0.000259704 s, excluding database/orchestration work. **Zero paid API calls and zero external provider requests** occurred in this benchmark. Timing differences are descriptive.

Model `qwen3.5:4b`, local artifact digest `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`, Ollama 0.33.3. Temperature zero, thinking disabled, context 8192, at most 256 generated tokens per request, 8 inference calls and 12 tools per rollout. Model weights were not changed.

## Separate development and design costs

Development smoke, seed 99901, is excluded from final results: **23 actual local calls**, **25,065 input tokens**, **1,456 output tokens**. It contains two training cases and one outage case under the three conditions. A training case stored correctly but omitted readback; this failure remains recorded. An out-of-scope conflict proposal in the development harness was not a usable rule for the current source; the final runner explicitly rejects scope mismatch. Its original source snapshot and logs are preserved. Benchmark plus development therefore used **786 local inference calls**; their scores are never combined.

The earlier, separately authorized Jev design review made **one paid provider request**, using 2,281 input and 179 output tokens; the monetary charge is unknown. It is retained under `reviews/jev-prompt-20261012/` and is not benchmark or development inference consumption. No further paid calls, installations, downloads or GitHub publication occurred.

## Verification and delivery limits

**53 tests passed on Linux and native Windows with UTF-8 explicitly enabled.** Windows initially exposed an encoding mismatch in the older decimal-format demo; the new Windows launcher uses `python -X utf8`. No frozen experimental code or original score was changed to address it.

Full offline verification succeeded on both hosts: **195 actual model-driven rollouts replayed**, including **180 final rollouts**, **763 captured inference calls verified**, proposals/gates and treatment memory rechecked, and **180 scripted reference controls replayed**, with **zero new model or remote calls**. Scripted reference completions were 30/60 without memory and 57/60 for each memory treatment, using the same actual available memory; these are separate controls, not language-model results.

```bash
python3 -m experience_forge reuse-verify --output runs/reuse-milestone-20261012
```

In the portable archive use `--output evidence/reuse-complete`. On Windows enable UTF-8: `python -X utf8 -m experience_forge reuse-verify --output evidence/reuse-complete`. Historical 0.3 source and evidence were also reverified: 280 captured rollouts and 1,234 calls, no new calls.

Post-run browser validation used existing Microsoft Edge under Windows at **1280 px and 390 px**. The derived viewer fit both viewports, disclosure toggles worked, and there were zero page errors or remote page requests. Screenshots and checks are recorded separately under `reports/`. The original viewer had mobile overflow from the long footer digest; its frozen evidence remains preserved. The derived viewer only clarifies the readback column, wraps long footer hashes for mobile layout and supplies a provenance note. Its linked JSON/JSONL copies have identical hashes to the original data. The frozen original viewer remains available with its collection-time limitations.

Native Windows model inference, other models, independent external datasets/replication, hosted CI and publication remain unverified. A useful next study would separate exact memory-reference errors and skipped readback from memory quality with a new frozen protocol; this completed pilot must not be retroactively rescored or rerun to claim improvement.
