# Changelog

## 1.4.0

- Quota advice weighs usage against time to reset: `conserve` (80%+) and `stop` (95%+) apply only when the remaining quota share is smaller than the remaining time share of that window (5h / 7d).
- Each window in a query returns `time_remaining_percentage` and its own `advice`; hook summaries and the installed CLAUDE.md guidance describe the pace rule.

## 1.3.0

- Return session-scoped context usage, remaining percentage and capacity in queries and hook summaries.
- Handle missing, invalid, stale and older records without estimating token use or auto-compacting.

## 1.2.0

- Return prompt cache expiry and remaining seconds in quota queries.
- Request one brief progress checkpoint per near-expiry window at live tool boundaries, subject to quota advice.
- Skip stale/missing/expired cache and stop/unknown quota; no model timers or session restarts.

## 1.1.0

- Add a compact quota plugin command and private session-scoped local reader service for Linux/macOS.
- Preserve existing statusline rendering; return unknown for missing/stale/expired data and ambiguity for multiple sessions.
- Add local zero-model watch, advisory checkpoint guidance, scoped backups and rollback.

## 1.0.0

- Enhanced fork of [Astro-Han/claude-pace](https://github.com/Astro-Han/claude-pace), retaining its MIT license and attribution.
- Show prompt-cache TTL and expiry using Claude Code's supplied `prompt_cache` fields.
- Show time since the last main-session assistant response with API usage; tool results do not reset this timer.
- Handle malformed input and non-object settings gracefully.
- Keep optional session IDs from shifting TSV fields and hiding cache expiry.
- Restore upstream Windows-path normalization; add `workspace.current_dir` fallback.
- Add a settings-preserving installer, bilingual docs and cross-platform CI.

Upstream release history is in [docs/UPSTREAM_CHANGELOG.md](docs/UPSTREAM_CHANGELOG.md).
