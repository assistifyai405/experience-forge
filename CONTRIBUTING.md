# Contributing

Start with an issue describing the behavior, reproduction steps and the evidence you expect to change. Small documentation, test and tooling fixes are welcome. Do not add provider credentials, personal data or model weights.

Run these offline checks from the checkout:

```bash
python -X utf8 scripts/offline_tests.py
python -X utf8 scripts/verify_publication.py
```

The test runner denies Python network connections. Scripted controls test integration; they are not live model results. Captured-evidence replay also denies network and performs no inference. Hosted CI is configured for Ubuntu and Windows on Python 3.11 and 3.14.

Experimental modules are bound to source hashes in the recorded protocol. Changing an experimental module means the old pilot must be replayed with its matching archived source. Preserve old evidence and create a new versioned protocol for a changed experiment. Do not weaken verification, change old grades or tune fixtures/prompts using final labels.

For new studies, freeze seeds, information boundaries, limits and scoring before inference. Keep development tasks separate, report failures/null effects and account for shared training costs. No automatic retry after uncertain provider outcomes. The live runner accepts only already-installed, non-cloud loopback models and never downloads them.

Specify the model artifact digest and runtime for live claims. Report actual retrieval, evidence-supported use, committed state and readback separately. Treat seeds as independent units; do not present tasks within one seed as independent replications. A correct guard is an execution control, not proof of model learning.
