# Captured pilot, no inference required

`reuse-complete.zip` contains the unchanged complete 0.4 pilot: original requests/responses, 195 agent rollouts, proposals, gates, SQLite condition memory, frozen fixtures/protocol, reference controls, runtime identity, reports and manifest. `checksums.json` binds the compressed artifact.

Run `python -X utf8 scripts/verify_publication.py` from the repository root. It checks the ZIP fingerprint, safely extracts it to a temporary directory and independently replays the actual captured model decisions with network connections denied. No API keys, Ollama installation, model downloads or inference are required.

The recorded model outputs are evidence from the reported local run, not model weights. The scripted reference controls are separate from model scores. See [the protocol](../docs/REUSE-PROTOCOL.md) and [results](../docs/REUSE-RESULTS.md).

The full publication release package additionally retains the prior 0.3/0.2 snapshots and development evidence. Historical manifests and experimental sources stay unchanged. Personal workstation metadata outside experimental traces is omitted or anonymized, as listed in `PUBLICATION-PROVENANCE.json`.
