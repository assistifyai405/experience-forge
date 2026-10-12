# Daily use in every local workchat

The daily adapter recalls source-backed work lessons before a task and stores useful
observations after completion. It reuses the real Experience Forge `canonical` and
`fingerprint` primitives. It is separate from the unchanged connector-calibration
pilot; its integration tests are not new model-performance measurements.

## Explicit local installation

From a trusted Experience Forge checkout, run:

```bash
python -m daily_workchat.install
```

This adds a marked block to your global Codex `AGENTS.md`, installs an implicitly
invocable skill, and registers four local MCP tools. Existing settings are preserved
and backed up. If a server already points to a different host, installation stops
rather than replacing it. You can choose `--codex-home` and `--skills-dir` explicitly.
The MCP server starts from its absolute script path, so unrelated working directories
are supported. Start a new local chat or reload the application to discover its tools.
A registered server is not proof that a particular chat has called it.

Global instructions apply across project and chat titles. Their supported behavior is
explained in [OpenAI's AGENTS.md documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md).
Project overrides can affect the resulting instruction set; check the instructions
actually loaded by the chat. This is a standing workflow on use, not a scheduled job
that opens dormant chats every day.

## Tools and fallback

- `forge_begin`: recall lessons at the start of a task and record usage.
- `forge_recall`: search applicable, intact lessons.
- `forge_remember`: save a useful observed lesson with actual evidence files.
- `forge_status`: inspect your local bank and usage counts.

If an existing chat has not loaded the tools, use the CLI from the checkout:

```bash
python -m daily_workchat.forge_daily begin --project . --chat your-actual-chat-id --query "release checks"
python -m daily_workchat.forge_daily remember --help
python -m daily_workchat.forge_daily status
```

Replace the example chat identifier with the actual task/chat ID. The current project
path controls retrieval scope. The default bank lives under your user data directory,
not inside the repository. Set `EXPERIENCE_FORGE_DATA_DIR` for a chosen private location.
A `--store` override is available for CLI tests. Do not commit your database or usage logs.

Choose one host's MCP server as the shared bank endpoint when using multiple runtimes.
Do not simultaneously open one SQLite file directly from different operating systems.
The author's local Windows setup delegates its server to WSL; that workstation-specific
configuration is deliberately omitted from the public repository.

## Evidence and privacy

Lessons record source snapshots with SHA-256 and Experience Forge fingerprints. Missing
or changed evidence and altered lesson payloads are rejected. Normal scope is a single
project; portable selection is explicit and intended for abstract workflows. Integrity
checks do not establish semantic correctness or current applicability: the agent must
check those. Stored text never authorizes spending, publishing or sending messages.

Only useful summaries and observed evidence are saved. Complete chats, personal
configuration and the author's memory bank are not part of this release. Credentials
and obvious authentication payloads are rejected; pattern checks cannot catch every
sensitive value. Follow your organization's data policy before saving anything.

Ordinary ChatGPT web/mobile or cloud chats require a separately connected app and
appropriate instructions. A local installation does not connect them automatically.

## Verify and remove

```bash
python -X utf8 scripts/offline_tests.py
python -X utf8 scripts/verify_publication.py
```

To disable the workflow, remove its marked instruction block, its own MCP section and
its skill folder. Preserve later settings; do not restore a whole old configuration
blindly. Keep the private bank if you want to retain your lessons.
