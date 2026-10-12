# 0.5.1 — exact replay runtime and project scopes

Fixes the public compatibility claim: exact captured replay uses Python 3.14,
matching the original floating-point aggregate arithmetic. Python 3.11 remains
supported for the daily adapter and unit controls. The CI matrix makes this
separation explicit; no original experiment source, trace, score or outcome is changed.

POSIX project-name case is now preserved during daily-memory scope comparison,
so differently cased project paths do not share project-specific lessons.
Windows-mounted scopes retain their existing case-insensitive normalization.

Supersedes 0.5.0. Daily integration and its privacy boundaries are described in
[the 0.5.0 notes](RELEASE-NOTES-0.5.0.md) and [setup instructions](DAILY-WORKCHAT.md).
