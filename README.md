# Claude Statusline Plus

A two-line Claude Code statusline with quota pace, context usage, prompt-cache expiry and time since the last model response.

[简体中文](README.zh-CN.md) · [Upstream](https://github.com/Astro-Han/claude-pace) · [MIT license](LICENSE)

An enhanced fork of **Astro-Han/claude-pace**, with the original author and license retained. The additional cache and activity indicators come from a version used on macOS and Ubuntu. This project is not affiliated with Anthropic.

```text
Opus (200K) high    | my-project (main) 2f +12 -3
██░░░░░░░░ 20% 200K | 5h 25% ⇡5% 4h 0m  7d 40% ⇡12% 5d 0h  cache 2m  last 10m
```

Illustrative data; percentages above are not a real account's usage.

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
```

Inherited regression tests additionally use Perl. CI runs the suites on macOS and Linux. The added tests cover quota/cache separation, activity timestamps, missing fields, malformed input, and preservation of unrelated installer settings.

## Credits and license

The quota pace renderer, context handling, Git display and cache protections originate in [Astro-Han/claude-pace](https://github.com/Astro-Han/claude-pace). This fork adds cache/activity indicators, defensive input handling, installer tooling and bilingual docs. See [NOTICE](NOTICE), [LICENSE](LICENSE) and [CHANGELOG](CHANGELOG.md).
