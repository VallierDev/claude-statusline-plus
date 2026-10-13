---
description: Read this session's reported Claude quota with one small local command
allowed-tools: Bash(~/.local/bin/claude-quota *)
---

Run `~/.local/bin/claude-quota --compact --session "${CLAUDE_SESSION_ID}"` exactly once. Claude Code substitutes the current session ID; never substitute another session. Report its result in at most two short sentences: 5h/7d remaining percentage, reset countdown, and advice. Do not research, read transcripts, or calculate token counts. If the command is unavailable, say the local quota service must be installed. If unknown or ambiguous, say so; do not select another session/account or assume full quota. If the current session ID is not substituted, return unknown; do not guess.

If the user asks for periodic checking, explain that the statusline publishes every 60 seconds and `~/.local/bin/claude-quota --watch --compact --interval 60` polls locally without model calls. Do not run an endless watch inside a blocking Bash tool or schedule repeated model invocations. Read once at task checkpoints; the model's reply still uses tokens.
