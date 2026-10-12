# First real-agent milestone — 12 October 2026

**Built and executed:** one genuine local model-driven tool agent, one synthetic task family, and all three memory treatments. **The pilot does not demonstrate a higher completion rate than no memory.** It does show that accepting incorrect lessons can harm completion and that qualification rejected those incorrect rules in this run.

Recorded run: `runs/agent-milestone-20261012/`. The release archive also includes the same evidence under `evidence/agent-milestone/`.

## Live results

| Treatment | Correct, single-write, verified completion | Transfer model calls | Transfer tool calls | Input tokens | Output tokens | Transfer wall time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| No memory | **9/16** | 77 | 61 | 65,653 | 2,574 | 41.64 s |
| Unvalidated memory | **7/16** | 57 | 41 | 52,256 | 4,102 | 59.08 s |
| Validated memory | **9/16** | 73 | 57 | 63,259 | 2,864 | 45.37 s |

Shared learning, charged equally to each treatment: **25 model calls**, **19,309 input tokens**, **731 output tokens**. Physically collected once: 4 training episodes and 4 model-generated proposals. The table above reports transfer consumption only. Per-treatment model calls including the assigned shared learning are 102, 82 and 98 respectively. They must not be summed as physical calls because the common stage is shared.

Total physically executed benchmark inference: **232 model calls**, **200,477 input tokens**, **10,271 output tokens**. Complete run wall time: **164.70 seconds**. API charges: **zero**; all inference used loopback HTTP to an installed local model. There were no experiment requests to a remote provider.

Qualification accepted **one** model-generated affine rule and rejected **three**, using **eight independent numeric examples and zero model calls**. No incorrect rules were manually planted in the live comparison. The rules came from actual model responses. Artificial negative controls exist only in unit tests and are not included as live results.

Paired completion against no memory:

- Unvalidated memory: 1 improved case, 3 worsened cases, 12 ties.
- Validated memory: 0 improved cases, 0 worsened cases, 16 ties.

Per trial, no memory and validated memory both scored 7/8 then 2/8. Unvalidated memory scored 5/8 then 2/8. This large difference between the two authored datasets is an additional reason to avoid statistical claims from this pilot.

## What the evidence supports

- The model genuinely chose tool calls, wrote and read SQLite state, and proposed coefficients from completed experiences.
- Three actual incorrect proposals were rejected before reuse by validated memory.
- One correct model-generated rule persisted through reopening SQLite and was available to new task values.
- Validated memory matched baseline completion with 4 fewer inference calls across 16 final cases. Token totals also differed; wall time was **higher**, so this run does not support a claim of faster execution.
- All final cases, including failures, are reported. None were dropped, repaired in place or rerun to improve the score.

## Failures and what to improve next

The agent frequently derived a wrong scale or reversed an offset sign. Several failed rollouts also saved a guessed quantity after the arithmetic tool reported that the chosen rule was unsupported. In the second trial's missing-input case, the no-memory and validated agents attempted a prohibited write; the environment blocked it and the grader counted the attempt as failure.

Qualification filters bad remembered coefficients, but it does not fix fresh reasoning mistakes or guarantee correct tool behavior. The next development step should evaluate better model reasoning and consistency checks on a **new, separately frozen suite**, while keeping these original outcomes intact. A deterministic reference solver and a stronger existing learning baseline would also help quantify the task's difficulty and the incremental value of memory.

## Reproduction and verification

```bash
python3 -m unittest discover -s tests -v
python3 -m experience_forge agent-verify --output runs/agent-milestone-20261012
```

To run fresh real inference on an already-installed local model, choose a new destination:

```bash
python3 -m experience_forge agent-benchmark --seed 31415 --trials 2 --output runs/my-new-comparison
```

Model: `qwen3.5:4b`, 4.7B parameters, Q4_K_M. Artifact digest: `2a654d98e6fba55d452b7043684e9b57a947e393bbffa62485a7aac05ee4eefd`. Runtime: Ollama 0.33.3. Python: 3.14.4 on the local Linux/WSL execution host. Final protocol: dataset seeds 31415 and 31416, temperature 0, thinking disabled, 8192 context tokens, 256 generated tokens per call, maximum 6 calls and 8 tool actions per rollout.

**26 unit/contract tests passed.** These use scripted controls for isolated behavior and remain separate from the live results above. Model-free evidence verification regenerated all labels and replayed **52 rollouts**, of which **48** were final transfer rollouts, against **232 captured model calls**. No new model requests were made during verification.

Native Windows execution, visual browser rendering, hosted GitHub Actions, other models and external replication remain unverified. GitHub publication has not occurred. The functional form and tool scaffolding are authored, and this pilot changes external typed memory rather than model weights. It is a first engineering milestone, not evidence of general self-improving intelligence.
