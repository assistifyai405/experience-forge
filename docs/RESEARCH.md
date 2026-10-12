# Research brief — original v0.1 scope, 12 October 2026

This historical brief describes the initial scripted demonstration. Version 0.2 adds actual local model inference, typed model-generated affine skills and a three-treatment pilot. See [the agent protocol](AGENT-PROTOCOL.md) and [recorded results](AGENT-RESULTS.md) for the current milestone; v0.1's no-model boundary remains valid for its original demo.

## The problem worth studying

Reliable continual learning from interaction is a useful direction, but it is not the single missing ingredient that guarantees superintelligence. Existing systems can already learn skills or improve prompts. The unresolved practical challenge is trustworthy improvement across changing tasks: distinguishing useful lessons from shortcuts, retaining old capabilities, handling uncertain feedback and demonstrating transfer.

## Primary sources

- [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366), Shinn et al. (2023). Uses reflective linguistic feedback in episodic memory to improve later trials without updating model weights. This establishes that experience-based adaptation is not new.
- [Voyager: An Open-Ended Embodied Agent with Large Language Models](https://arxiv.org/abs/2305.16291), Wang et al. (2023). Combines curriculum, an executable skill library and environment feedback in Minecraft, including transfer to a new world. A skill library itself is not an original contribution here.
- [Build an Agent Improvement Loop with Traces, Evals, and Codex](https://developers.openai.com/cookbook/examples/agents_sdk/agent_improvement_loop), OpenAI Cookbook. Demonstrates an agent improvement workflow using traces and evaluations. This prototype does not replace that workflow or claim that OpenAI lacks improvement loops.
- [Experience Replay for Continual Learning](https://arxiv.org/abs/1811.11682), Rolnick et al. (2018). Studies retaining earlier knowledge while learning new tasks through replay. Our retained test cases are an engineering analogy; this demo does not reproduce the paper's neural training experiments.

## Hypothesis and experimental boundary

Hypothesis: within an authored finite rule language, a learner can derive a candidate from failed episodes; retained and qualification examples can reject broad shortcuts; a promoted candidate can improve a separate synthetic transfer set.

The proposer sees training only. Qualification labels select candidates and are not reported as blind transfer. Transfer is evaluated after freezing the selected skill. The author controls the complete synthetic distribution and hypothesis language, so this is a demonstration, not independent evidence of general intelligence.

Success: a positive transfer gain, zero observed case-level regressions at qualification, and preserved behavior after database reload. Negative controls must fit the training errors but fail qualification. Conflicting labels must block learning; missing qualification evidence must block promotion. Untrusted text must remain input data, not executable instructions.

## What remains unproven

No actual LLM learning or model comparison has run. There are no weight updates, open-ended feature discovery, learned world model, general causal reasoning, statistical claims across task families, or native Windows validation. Better results in the included synthetic family do not establish usefulness on arbitrary real tasks. A small bounded demo alone should not be marketed as a major AI breakthrough.
