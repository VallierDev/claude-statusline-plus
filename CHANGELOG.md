# Changelog

## 1.0.0

- Enhanced fork of [Astro-Han/claude-pace](https://github.com/Astro-Han/claude-pace), retaining its MIT license and attribution.
- Show prompt-cache TTL and expiry using Claude Code's supplied `prompt_cache` fields.
- Show time since the last main-session assistant response with API usage; tool results do not reset this timer.
- Handle malformed input and non-object settings gracefully.
- Keep optional session IDs from shifting TSV fields and hiding cache expiry.
- Restore upstream Windows-path normalization; add `workspace.current_dir` fallback.
- Add a settings-preserving installer, bilingual docs and cross-platform CI.

Upstream release history is in [docs/UPSTREAM_CHANGELOG.md](docs/UPSTREAM_CHANGELOG.md).
