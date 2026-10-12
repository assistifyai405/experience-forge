# Preregistered first-agent milestone

Task family: synthetic quantity-import connectors. Each source/revision uses a hidden affine encoding `encoded = scale * quantity + offset`. The functional form is known in advance; the integer coefficients are not supplied in the task. An installed local language model chooses tools and derives reusable typed rules from its completed episodes.

## Treatments

1. `no_memory`: the agent sees no remembered rules.
2. `unvalidated_memory`: the agent receives structurally valid model-generated rules without checking their accuracy.
3. `validated_memory`: the agent receives those same proposals only after two distinct independent qualification cases pass and existing scoped rules have no observed regression.

Rules are retrieved by exact source and revision in both memory treatments. Prompt wording, tools, arithmetic support, missing-input behavior and all execution ceilings are identical. Validation status is not displayed to the agent, so the experiment isolates selection rather than a different trust instruction.

## Shared experience and budget

Each trial collects one real agent episode for each of two unknown source contracts, then makes one real model proposal per source. This common curriculum is physically executed once and charged equally to all treatments. It is an explicit design choice: the experiment tests reuse and filtering after a common experience stream, not independent multi-step online learning curricula.

Qualification is deterministic arithmetic on typed rules and uses no model calls. Its extra CPU work is still a deployment cost of the validated treatment. Report tables separate common learning from final task consumption. Equal execution ceilings are not a claim that actual token counts or elapsed times are equal.

Default ceilings: 6 model calls and 8 executed tool calls per rollout, 256 generated tokens per call, 8192 context tokens, temperature zero and the same trial seed across treatments. Source/revision-scoped memory is limited to two rules in every agent invocation. No model weights are updated.

## Frozen final comparison

The recorded milestone uses dataset seeds **31415 and 31416**, selected before running the final comparison. Per trial: 2 training cases, 4 qualification cases, 6 new known-contract task values, 1 unseen revision and 1 missing-input task. Thus the final comparison has **16 tasks per treatment, 48 live transfer rollouts in total**. Each rollout starts with fresh chat messages and an isolated SQLite world. Treatments share no writes or conversation state.

Final cases are shuffled per trial. Treatment order rotates per case to reduce server warm-up and cache bias. The protocol, complete fixture labels and hashes of all Python sources are frozen before the first benchmark inference request. Final labels are never passed to the agent, proposer or memory selector. The grader reads them only after each rollout. The author knows the generator; this is not an independent external or contamination-proof benchmark.

Success requires a correct actual saved value, exactly one write attempt, a successful readback and a completed model turn. Missing-input success requires no write. Completion prose alone earns no credit. All completed rollout failures remain in the report. Transport errors abort the run as incomplete without retry or automatic continuation; logs retain the started request.

There is no required winner or minimum improvement. A tie or regression is a valid result. With one small authored family and two trials, the output is a pilot, not a statistically powered claim of superiority.

## Development smoke test

Before freezing the final protocol, one no-memory training example with development seed 20261012 exposed confusion between a calibration target of 10 and the scale coefficient. The common instruction was clarified with the general two-point slope formula. No final comparison cases were used for that adjustment. Both memory treatments receive the same clarified instruction.

## Reproducibility and provenance

Every actual model request/response, seed, options, tool decision, state result, generated rule and qualification decision is recorded. Model-free verification regenerates oracle labels, checks qualification and stored memory, replays captured outputs through the actual tool implementation and recomputes the comparison. It makes no new inference calls and cannot establish deterministic reproduction of the language model itself.

The local adapter uses Ollama's documented [chat API](https://docs.ollama.com/api/chat), [tool-calling protocol](https://docs.ollama.com/capabilities/tool-calling), and [structured outputs](https://docs.ollama.com/capabilities/structured-outputs). Only existing local, non-cloud models on literal loopback endpoints are accepted. It never downloads a model or contacts a paid API.
