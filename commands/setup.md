---
description: Install Claude Statusline Plus without changing account or permission settings
allowed-tools: Bash, Read, Write, Edit
---

If the user wants the quota command/service, run `python3 "${CLAUDE_PLUGIN_ROOT}/service/install.py"` instead of replacing an existing quota wrapper with the display-only script. The installer preserves the renderer and other settings. Explain that new sessions load the quota guidance and command. Do not restart existing sessions.

Check `command -v jq`. If missing, ask the user to install jq and stop.
Read the current `~/.claude/settings.json`. Do not overwrite unrelated settings.
Back up existing settings and any existing `~/.claude/claude-statusline-plus.sh` before updating them.
Copy the bundled `${CLAUDE_PLUGIN_ROOT}/claude-pace.sh` to `~/.claude/claude-statusline-plus.sh` and make it executable.
Add or update only `statusLine`:

```json
{"type":"command","command":"~/.claude/claude-statusline-plus.sh","refreshInterval":60}
```

Do not change permissions, credentials, models, account state or any other key.
Do not download another script; install the exact bundled version.
Confirm installation. Explain that quota data appears only when Claude Code supplies it, usually after the first response. Suggest starting a new Claude Code session.
