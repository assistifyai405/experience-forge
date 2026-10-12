# Experience Forge 0.4.0 — publication candidate

An agent can retrieve evidence from a previous conversation and apply it to new connector values when fresh calibration is unavailable. This release makes that behavior observable and reproducible in a small controlled pilot.

- One real local `qwen3.5:4b` tool agent; one authored affine connector task family.
- Three memory treatments, matching prompts/tools/limits, five frozen seeds, 180 final rollouts.
- 29/60 tasks completed without memory; 41/60 under both unvalidated and validated memory.
- 21/30 supported reuse opportunities under each memory treatment; 13/30 fully committed and read back. Eight correctly stored results per memory treatment lacked required readback.
- No wrong commits. Qualification did not improve final task completion; two rejected conflicting-memory normalization attempts disappeared with filtering.
- 763 actual local inference calls; full original captures retained. The separate development smoke and earlier one-call paid Jev design review are excluded from final scores.
- 53 unit/integration checks, full captured replay, source/evidence hashes, Windows UTF-8 launcher and a standalone desktop/mobile viewer.
- Offline CI configured for Ubuntu/Windows, Python 3.11/3.14, with full action pins and no model/network access in Python test/replay steps.

Read [the protocol](REUSE-PROTOCOL.md), [all results and limits](REUSE-RESULTS.md) and [attribution](ATTRIBUTION.md). No superiority, general intelligence, hosted-CI success or external replication is claimed. Hosted checks can only be observed after approved publication.

Public assets are a privacy-reviewed derivative of the original local package. Experiment source and raw model traces remain byte-identical; workstation metadata outside those traces is omitted/anonymized and documented in the provenance file. The original private archives are retained locally.
