#!/usr/bin/env python3
"""Install a private Linux/macOS user service, retaining current renderer/settings."""
import json
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from quota import atomic

home = Path.home()
root = home / '.local/share/claude-quota'
settings = home / '.claude/settings.json'
linux = sys.platform == 'linux'
unit = home / ('.config/systemd/user/claude-quota.service' if linux else 'Library/LaunchAgents/com.vallierdev.claude-quota.plist')
cli = home / '.local/bin/claude-quota'
instructions = home / '.claude/CLAUDE.md'
original = json.loads(settings.read_text()) if settings.exists() else {}
old = original.get('statusLine') or {}
wrapper_command = f'{shlex.quote(sys.executable)} {shlex.quote(str(root / "quota.py"))} capture-render'
is_update = old.get('command') == wrapper_command
if old and (old.get('type') != 'command' or not isinstance(old.get('command'), str)):
    raise SystemExit('Unsupported existing statusline; no changes made.')
backup = home / '.claude/backups/claude-quota' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
backup.mkdir(mode=0o700, parents=True)
paths = [settings, unit, cli, instructions, root/'quota.py', root/'renderer.json', root/'claude-pace.sh']
manifest = []
for i, p in enumerate(paths):
    manifest.append({'path': str(p), 'backup': str(backup/str(i)), 'present': p.exists(), 'mode': p.stat().st_mode & 0o777 if p.exists() else 0o600})
    if p.exists():
        shutil.copy2(p, backup/str(i))
        os.chmod(backup/str(i), 0o600)
atomic(backup/'manifest.json', manifest)
root.mkdir(mode=0o700, parents=True, exist_ok=True)
shutil.copy2(Path(__file__).with_name('quota.py'), root/'quota.py')
shutil.copy2(Path(__file__).parent.parent/'claude-pace.sh', root/'claude-pace.sh')
# Older installer used 'python3'; detect that wrapper too when updating.
if old.get('command') == f'python3 {shlex.quote(str(root / "quota.py"))} capture-render':
    is_update = True
if not is_update:
    renderer = old.get('command') or f'bash {shlex.quote(str(root/"claude-pace.sh"))}'
    atomic(root/'renderer.json', {'command': renderer})
cli.parent.mkdir(parents=True, exist_ok=True)
cli.write_text('#!/bin/sh\nexec '+shlex.quote(sys.executable)+' '+shlex.quote(str(root/'quota.py'))+' "$@"\n')
cli.chmod(0o700)
unit.parent.mkdir(parents=True, exist_ok=True)
if linux:
    unit.write_text('[Unit]\nDescription=Claude Code private quota reader\n\n[Service]\nExecStart='+sys.executable+' '+str(root/'quota.py')+' serve\nRestart=on-failure\nUMask=0077\nNoNewPrivileges=true\nPrivateTmp=true\n\n[Install]\nWantedBy=default.target\n')
else:
    with unit.open('wb') as f:
        plistlib.dump({'Label':'com.vallierdev.claude-quota', 'ProgramArguments':[sys.executable,str(root/'quota.py'),'serve'], 'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':10,'Umask':0o077},f)
config = dict(old)
config.update(type='command', command=wrapper_command, refreshInterval=60)
original['statusLine'] = config
atomic(settings, original)
marker = '<!-- claude-quota-service -->'
text = instructions.read_text() if instructions.exists() else ''
guidance = '''\n\n<!-- claude-quota-service -->
## Quota-aware work on this machine
Before a long autonomous task and at natural checkpoints (about every 10 minutes during sustained work), invoke `/pace-statusline-plus:quota` once: the command uses Claude Code's substituted own session ID. If the plugin is unavailable, use `~/.local/bin/claude-quota --compact --cwd "$PWD"` without guessing when ambiguous. Keep the response short; do not create model timers or repeated reasoning turns just to poll. Background local polling is available with `~/.local/bin/claude-quota --watch --compact --interval 60` and calls no model.
This reads reported Claude Code statusline quota, not token counts or an independently refreshed account balance. If multiple sessions match, use `--list` then an explicitly identified own session ID with `--session`; never assume a different session/account is yours. Missing/stale/expired windows mean unknown, not full quota. Account switches may keep cached input: wait for an actual Claude response before trusting it.
Judge each window by pace, not by remaining quota alone: compare the remaining quota share (100% - used) with the remaining time share (time to reset / window length: 5h or 7d). Conserve (batch tools, avoid optional analysis) only when a window is at 80%+ used AND its remaining quota share is smaller than its remaining time share; at 95%+ used under the same condition, finish a safe checkpoint and report the reset time, deferring discretionary work until reset. If the remaining quota share is at least the remaining time share (e.g. 16% left with 4% of the week left), work normally. These are advisory defaults, not automatic enforcement. A user can explicitly override them. Do not claim automatic pause/resume exists or bypass provider limits.
<!-- /claude-quota-service -->
'''
end_marker = '<!-- /claude-quota-service -->'
start, end = text.find(marker), text.find(end_marker)
if start >= 0 and end >= start:
    text = text[:start] + guidance.strip() + text[end+len(end_marker):]
else:
    text += guidance
instructions.write_text(text)
instructions.chmod(0o600)
if linux:
    subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    subprocess.run(['systemctl','--user','enable','claude-quota.service'],check=True)
    subprocess.run(['systemctl','--user','restart','claude-quota.service'],check=True)
else:
    domain = f'gui/{os.getuid()}'
    subprocess.run(['launchctl','bootout',domain,str(unit)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    subprocess.run(['launchctl','bootstrap',domain,str(unit)],check=True)
print('Installed; backup='+str(backup))
