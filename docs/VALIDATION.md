# Original v0.1 local validation — 12 October 2026

This document preserves evidence for the original scripted demo. Current agent-milestone validation is recorded in [AGENT-RESULTS.md](AGENT-RESULTS.md).

Environment: Python 3.14.4 on the local Linux/WSL execution host. No dependencies installed. No model or network calls were made by the experiment.

- `python3 -m unittest discover -s tests -v`: **12 tests passed**, including 20 different fixture seeds in the same authored task family.
- `python3 -m experience_forge demo --output runs/first-release-20261012`: **passed**. Training improves from 0/12 to 12/12. Separate transfer improves from **27/51 to 51/51**. Three candidates are rejected before the fourth is accepted. Skill version 1 survives a fresh SQLite connection.
- `python3 -m experience_forge verify --output runs/first-release-20261012`: artifact SHA-256 hashes and fresh deterministic replay **passed**.
- Appending text to a temporary copy of `journal.json`: verification rejects the modified evidence with a nonzero exit. Original run preserved.
- Report JavaScript passes `node --check`. HTML evidence escapes injected markup.

Tests cover feedback contradictions, duplicate input leakage even under a different source name, absent evidence, misleading aggregate gains, environment shortcuts, rejected promotion, restart persistence, rollback, unsupported/untrusted input, deterministic repetition and refusal to overwrite existing runs.

## Evidence limits

This is an offline program-synthesis demonstration, not an actual LLM/agent performance measurement. The score comes from a deliberately designed synthetic family and fixed hypothesis language. Twenty seeds vary numeric values, not the family or language. The final transfer set is separate from proposal and qualification, but the author knows the complete generator. No claim of broad generalization or superintelligence is supported.

Native Windows execution, visual browser rendering and hosted GitHub Actions have not been tested. The HTML viewer is self-contained and ready to open locally. The `.cmd` launcher and workflow are supplied but unverified in those environments. GitHub publication has not occurred.
