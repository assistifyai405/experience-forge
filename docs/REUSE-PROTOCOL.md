# Frozen experience-reuse pilot — version 0.4

This study tests external information reuse after a fresh conversation and isolated task state. It does not train weights or demonstrate general intelligence. The prior 0.3 ceiling result remains archived under `history/v0.3.0/experience-forge` with its matching source and original evidence.

## Fixed comparison

Five seeds **60701–60705**, checked against previous recorded run protocols before execution. Per seed: three common training episodes (two consistent contracts and one contract with conflicting observations), six qualification fixtures (two per training contract), and twelve final tasks under all three memory treatments. This yields 60 tasks per treatment, 180 final model rollouts, 15 shared training episodes and 15 actual model proposal requests. Development seed **99901** is separate and excluded from final scores. Contract tests use separate synthetic seeds and scripted controls, excluded from live quality claims.

| Final category | Per seed | Desired state | Available evidence |
| --- | ---: | --- | --- |
| Known contract, calibration unavailable | 6 | Correct single commit and readback | Previously observed experience only if treatment memory supplies it |
| Changed revision | 1 | No commit | Old revision may be retrieved but is invalid |
| Unknown contract | 1 | No commit | No matching experience and no fresh calibration |
| Missing input | 1 | No commit | Missing encoded quantity |
| Conflicting prior observations | 1 | No commit | A stored candidate may be present, but conflicting evidence cannot authorize it |
| Online control | 2 | Correct single commit and readback | Fresh calibration is available to every treatment |

The same desired state is graded in each treatment. For outage tasks, the no-memory condition intentionally has insufficient evidence: appropriate uncertainty there is counted separately from completion of the desired import. The information difference is the intervention, not evidence that memory made a model generally smarter. No positive winner is required.

## Information boundaries

| Component | Receives | Excluded |
| --- | --- | --- |
| Initial agent prompt | Current public input, source/revision, supplied affine formula, generic instructions | Historical rules/observations, condition name, category, gold target, training transcript |
| Memory retrieval tool | Reopened treatment items for the current source, including visible revision mismatch | Other treatments, other seeds, global training lookup, final gold labels |
| Fresh calibration/helper | Current observations when service is online | Historical fallback and gold coefficients |
| Normalization/write control | Explicitly retrieved unchanged item or previously read fresh observations | Rule selection, candidate repair, global history lookup, final labels |
| Proposal model | Only public input, observed tool events and final training text | Training grade fields, qualification/final labels |
| Qualification | Fixed independent qualification cases and candidate evidence consistency | Final outcomes or final labels |
| Grader | Frozen expected state after the rollout | Cannot provide answers through agent tools |

A candidate item contains the actual model-proposed rule, calibration observations found in its training tool trace, training case/input identity and a trace digest. It has a content hash and derived stable ID. No observation is silently filled from the generator when the agent did not read it. Unvalidated memory receives all structurally valid scoped proposals; validated memory receives only candidates passing independent qualification and observed-evidence consistency. Rejected and malformed proposals remain in evidence.

Each final rollout reopens the treatment SQLite database read-only, starts fresh messages and a separate in-memory SQLite write world, and receives no remembered coefficients in its initial prompt. A recalled item can be used only after retrieval, for identical source/revision and a new input. Its candidate coefficients must be the ones explicitly selected by the agent. Exact arithmetic checks every supplied observation without choosing or correcting the candidate. Failed normalization invalidates previous proof; a write proof binds input, revision, quantity and observation digest. Blocked and invalid attempts remain visible even after successful recovery.

## Observable outcomes

Primary reuse denominator: **30 known-contract outage opportunities per treatment**. Report separately:

1. An item was explicitly retrieved, with traceable ID and hash.
2. Historical normalization was attempted with an explicit memory ID.
3. Historical candidate normalization was accepted against observed evidence, without fresh calibration.
4. That use led to a correctly committed and verified value.

Repeated events are available in raw traces; primary proportions count rollouts once. Accepted use and successful commit are distinct. Wrong guessed values cannot qualify as observed reuse. No claim is made about unobserved internal memory use.

Report completion per category and seed, required abstention, unsupported abstention, wrong commits, unsafe/blocked writes, failed normalization, calibration requests, actual calls, tokens, tools and elapsed time. Same limits for every treatment: **8 model calls, 12 tool actions, 256 generated tokens per request, context 8192, temperature zero, thinking disabled**. Cases are seeded-shuffled; three-condition order rotates. Cache/order effects may remain. Shared training/proposal consumption is physically collected once and assigned equally when estimating a treatment's total controlled-study cost. Qualification CPU belongs to validated memory; provider consumption is zero for qualification.

## Freeze, interpretation and replay

Fixtures, complete protocol, tools, prompt and source hashes are saved before the first inference request. Final labels never tune prompts, seeds, gates or budgets. Source drift aborts finalization. A transport failure marks the run incomplete and retains requests, responses and costs; there is no retry or automatic resume of uncertain work. Start a changed experiment only with a new documented protocol and new cases.

Five authored seeds are the independent units. Paired completion differences are reported per seed, with mean, sample standard deviation and range. These descriptive quantities are not confidence bounds and do not establish statistical superiority. The five datasets, model and functional form limit generalization. A shared guard can remove commit differences between memories: failed normalization and attempts are necessary to distinguish candidate filtering from execution protection.

The deterministic reference uses the same available treatment evidence and tools, without model calls, and is excluded from model scores. `reuse-verify` regenerates fixture labels, rechecks proposals/qualification and persisted evidence, and replays every captured model output through the real tool world, checking original prompts and tools. It does not regenerate model outputs. The raw model journals, isolated-world events, proposals, gates, SQLite memory, progress and reports are hashed in a manifest.

```bash
python3 -m experience_forge reuse-benchmark --seed 60701 --trials 5 --output runs/NEW_DIRECTORY
python3 -m experience_forge reuse-verify --output runs/reuse-milestone-20261012
```

No downloads, installations, paid API calls or publication belong to this benchmark. The earlier one-call Jev design review is preserved separately under `reviews/jev-prompt-20261012/` and excluded from benchmark consumption. Native Windows model execution, rendered browser layout, hosted CI, other models and independent replication remain unverified.
