# Claude Statusline Plus

A two-line Claude Code statusline with quota pace, context usage, prompt-cache expiry and time since the last model response.

[简体中文（默认）](README.md) · [Upstream](https://github.com/Astro-Han/claude-pace) · [MIT license](LICENSE)

An enhanced fork of **Astro-Han/claude-pace**, with the original author and license retained. The additional cache and activity indicators come from a version used on macOS and Ubuntu. This project is not affiliated with Anthropic.

```text
Opus (200K) high    | my-project (main) 2f +12 -3
██░░░░░░░░ 20% 200K | 5h 25% ⇡5% 4h 0m  7d 40% ⇡12% 5d 0h  cache 2m  last 10m
```

Illustrative data; percentages above are not a real account's usage.

## Session context usage (1.3.0)

Quota queries and live hook summaries now include `context=63% remaining=37% capacity=1M`. JSON `context_window` contains status, used_percentage, remaining_percentage and context_window_size (token capacity). Values are session-scoped and reported by Claude Code, never inferred from cumulative input tokens. Missing data returns unknown; receipts older than 180 seconds return stale. Context capacity is separate from subscription quota and the auto-compaction threshold; no automatic compaction or restart is introduced. Rerun the service/plugin/live-hook installers to update; existing sessions use the output at the next tool boundary and can load the command with `/reload-plugins`.

## Cache countdown and brief keepalive (1.2.0)

Queries now include `cache=2640s`; JSON `prompt_cache` has `expires_at`, `remaining_seconds`, and `status` (warm/expired/unknown/stale). Quota `resets_at` remains separate. At tool boundaries, the opt-in live hook requests a one-sentence progress checkpoint in the next normal response when cache has 1–300 seconds left and quota advice is normal/conserve. It reminds once per reported expiry; stop/unknown quota or invalid cache never triggers keepalive.

This reuses the same session and normal model response, without an extra model timer. Only an actual cache-hit request may refresh cache; local reads do not. Model usage still costs tokens; refresh is not guaranteed. Idle sessions and sessions without tool boundaries are not automatically woken. Expired cache does not delete conversation context. Update the checkout then rerun the service, plugin and live-hook installers; Claude processes are not restarted.

## What it shows

| Indicator | Meaning |
| --- | --- |
| Model, context capacity, effort | Current Claude Code session configuration |
| Context bar | Context-window occupancy, separate from subscription quota |
| `5h` / `7d` | Used percentage, time until reset, and reset clock in your local timezone |
| `⇡` / `⇣` | Usage ahead of / behind the proportion of the window that has elapsed; a pace indicator, not a forecast |
| Git branch and changes | Working-tree identity, changed files and added/deleted lines |
| `cache` | Prompt-cache countdown when Claude Code supplies expiry data |
| `last` | Time since a main-session assistant response carrying API usage; tool results do not reset it |

## Using this in Claude Code

For the full feature set, run `python3 service/install.py` and `python3 service/install-plugin.py` from this checkout. Optionally run `python3 service/install-live-hook.py` for running-session reminders. Plugin installation alone does not start the local reader service. Use `/reload-plugins` in an existing session to load new commands, or use them in a new session. Do not run the display-only installer after installing the service wrapper.

Enter `/pace-statusline-plus:quota` in Claude Code to query the current session. The Bash fallback is `~/.local/bin/claude-quota --compact --cwd "$PWD"`; if ambiguous, use the plugin command or an explicitly identified own session ID. Tell Claude to use received hook reminders instead of repeating queries, conserve at 80% used, and checkpoint/defer discretionary work at 95%.

An existing monitor can check and resume the task once both windows report valid usage below 80%. Missing/stale/ambiguous readings and reset countdown expiry are not proof of recovery. This project does not wake idle models or resume stopped tasks; without an existing monitor, send a new instruction to check and continue. `--watch` only prints local changes and never sends a message to Claude. See the [Chinese usage guide](README.md) for copyable prompts.

## Live reminders without restarting (explicit opt-in)

Run `python3 service/install-live-hook.py` to add command-only PreToolUse/PostToolUse hooks. Existing hooks are preserved and settings are backed up. Claude Code normally watches settings changes, so running sessions can receive quota context at their next tool boundary. The hook checks at most once per minute and emits a compact reminder every ten minutes or on advice transitions (normal/conserve/stop/unknown). It never starts a model timer, blocks a tool, changes permissions, restarts sessions or forces automatic resume. Idle sessions receive it when they next use a tool. Local receipts in `~/.cache/claude-quota/hook` confirm hook execution, not compliance with advice. Remove only the entries pointing at `quota-hook.py` to disable; do not restore the entire settings backup over later changes.

## Quota command and local reader service (1.1.0)

`/pace-statusline-plus:quota` uses Claude Code’s `${CLAUDE_SESSION_ID}` substitution to run one compact local query for its own session and replies in at most two short sentences. From this checkout, install the Linux systemd user service or macOS LaunchAgent and the exact local plugin:

```bash
python3 service/install.py
python3 service/install-plugin.py
~/.local/bin/claude-quota --compact --cwd "$PWD"
~/.local/bin/claude-quota --list
~/.local/bin/claude-quota --compact --session <your-session-id>
```

Requires Python 3.9+ and Claude Code CLI, plus your existing statusline dependencies. The installer backs up affected files, preserves the existing renderer and other settings, and adds quota guidance to `~/.claude/CLAUDE.md`. It does not change hooks, credentials or permissions, or restart Claude sessions. New sessions load the plugin command and guidance; existing sessions may reload statusline settings but are not guaranteed to adopt the guidance.

The statusline forwards whitelisted session ID, directory and 5h/7d quota fields every 60 seconds. The service never reads credentials/conversations or calls Anthropic. It serves `/health` and `/v1/quota` through a private `0600` Unix socket, with no TCP listener: `$XDG_RUNTIME_DIR/claude-quota.sock` on Linux (default `/run/user/<uid>/claude-quota.sock`), `~/.cache/claude-quota/reader.sock` on macOS.

```bash
~/.local/bin/claude-quota --watch --compact --interval 60
```

This foreground watch prints changes until Ctrl-C and calls no model. Run it in a separate terminal, not as an endless blocking Claude tool. Guidance asks Claude to read once before long work and at natural checkpoints (roughly every 10 minutes of sustained work). Local polling costs no model tokens; model reads/replies still cost tokens. There is no automatic model wakeup or guaranteed token count.

Results are reported percentages, not token counts. Advice defaults to conserve at 80% used and checkpoint/defer discretionary work at 95%; this is advisory, not enforced stop/resume. Multiple matching sessions return `ambiguous` and require an explicitly identified session ID. Missing data, receipts older than 180 seconds and expired reset times return unknown, never assumed full quota. Receipt age is not provider freshness: timer refreshes may reuse Claude Code data, and account switches require a real response before trusting the new quota. No independent account balance query is performed.

Inspect with `systemctl --user status claude-quota.service` on Linux or `launchctl print gui/$(id -u)/com.vallierdev.claude-quota` on macOS. Linux persistence after logout depends on existing linger configuration; the installer does not change it. The macOS agent starts at user login.

To restore the installation backup without overwriting unrelated settings added later:

```bash
python3 service/rollback.py ~/.claude/backups/claude-quota/<backup-directory>
claude plugin uninstall pace-statusline-plus@pace-statusline-plus-local
```

Private service/plugin backups live under `~/.claude/backups/claude-quota` and `claude-quota-plugin`; never upload them. See [中文说明](README.md) for more detail.

## Install

Runtime: **Bash 3.2+**, **jq** and standard Unix utilities. Git is needed for the optional Git segment. macOS and Linux are the supported targets; Windows Git Bash has inherited path normalization but is not verified by this fork's CI.

Install jq if needed:

```bash
# macOS
brew install jq
# Ubuntu / Debian
sudo apt-get install jq
```

### Settings-preserving installer

The installer additionally needs Python 3.8+.

```bash
git clone https://github.com/VallierDev/claude-statusline-plus.git
cd claude-statusline-plus
python3 install.py
```

It installs `~/.claude/claude-statusline-plus.sh`, backs up your previous settings, and updates **only `statusLine`**. It does not change your model, permissions, account or other plugins. A 60-second refresh keeps countdowns moving between responses.

### Manual install

```bash
mkdir -p ~/.claude
cp claude-pace.sh ~/.claude/claude-statusline-plus.sh
chmod +x ~/.claude/claude-statusline-plus.sh
```

Merge this key into `~/.claude/settings.json`; do not replace the entire file:

```json
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/claude-statusline-plus.sh",
    "refreshInterval": 60
  }
}
```

### Claude Code plugin

```text
/plugin marketplace add VallierDev/claude-statusline-plus
/plugin install pace-statusline-plus@pace-statusline-plus-marketplace
/pace-statusline-plus:setup
```

The setup command installs the bundled script and updates only the statusline setting. Start a new session after installation.

## Quota and cache availability

Claude Code supplies quota data in `rate_limits` on stdin. According to the [official statusline documentation](https://code.claude.com/docs/en/statusline), this data is available for Pro/Max accounts and some gateway configurations, and only after the first API response; individual windows can be absent. A fresh or unsupported session therefore shows `--`, rather than a stale quota snapshot.

The cache countdown uses `prompt_cache.expires_at` supplied by Claude Code. An absent field is not treated as a guessed cache hit or a five-minute timer. `last` is an activity indicator, **not proof that a prompt cache remains valid**. Use a recent Claude Code version; the fork's added fields were verified with 2.1.296. Older versions degrade gracefully when fields are missing.

## Privacy and local files

The runtime script makes **no network requests** and reads **no authentication credentials**. It reads session JSON on stdin and local settings. When a session ID is supplied, it reads at most the last 400 lines of that session's local JSONL record to select the latest assistant-usage timestamp; it does not print conversation contents. Git metadata is cached briefly in a user-owned `claude-pace` directory under `$XDG_RUNTIME_DIR` or `~/.cache`.

Installation backups are stored locally under `~/.claude/backups/claude-statusline-plus` with restricted permissions. Settings backups can contain your own private settings: do not publish them. This repository contains only source, documentation and synthetic tests.

## Remove or restore

Remove the `statusLine` key to disable the statusline, or restore **just that key** from the backup path printed by the installer. `previous-statusline.json` records whether the key existed and its old value. Restoring an entire settings backup also reverts settings you changed later, so use a selective restore when appropriate. You can then delete `~/.claude/claude-statusline-plus.sh`.

## Development

```bash
bash -n claude-pace.sh
# Isolate HOME so tests never touch your Claude configuration.
test_home=$(mktemp -d)
HOME="$test_home" XDG_RUNTIME_DIR="" bash test.sh
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s service -p "test_*.py" -v
```

Inherited regression tests additionally use Perl. CI runs the suites on macOS and Linux. The added tests cover quota/cache separation, activity timestamps, missing fields, malformed input, and preservation of unrelated installer settings.

## Credits and license

The quota pace renderer, context handling, Git display and cache protections originate in [Astro-Han/claude-pace](https://github.com/Astro-Han/claude-pace). This fork adds cache/activity indicators, defensive input handling, installer tooling and bilingual docs. See [NOTICE](NOTICE), [LICENSE](LICENSE) and [CHANGELOG](CHANGELOG.md).
