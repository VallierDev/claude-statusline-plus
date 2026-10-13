#!/usr/bin/env python3
"""Explicit opt-in: enable quota reminders for running sessions via settings watcher."""
from datetime import datetime,timezone
import json
from pathlib import Path
import shlex
import shutil
import sys
from quota import atomic
home=Path.home(); root=home/'.local/share/claude-quota'
settings=home/'.claude/settings.json'
d=json.loads(settings.read_text())
if d.get('disableAllHooks'): raise SystemExit('Hooks disabled; no changes made.')
hooks=d.setdefault('hooks',{})
if not isinstance(hooks,dict): raise SystemExit('Unsupported hooks configuration; no changes made.')
backup=home/'.claude/backups/claude-quota-live'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
backup.mkdir(mode=0o700,parents=True)
shutil.copy2(settings,backup/'settings.json');(backup/'settings.json').chmod(0o600)
root.mkdir(mode=0o700,parents=True,exist_ok=True)
source=Path(__file__).parent/'quota-hook.py'
shutil.copy2(source,root/'quota-hook.py')
command=shlex.quote(sys.executable)+' '+shlex.quote(str(root/'quota-hook.py'))
for event in ('PreToolUse','PostToolUse'):
    groups=hooks.setdefault(event,[])
    if not isinstance(groups,list): raise SystemExit('Unsupported event configuration; no settings changed.')
    if not any(any(h.get('command')==command for h in g.get('hooks',[])) for g in groups):
        groups.append({'matcher':'','hooks':[{'type':'command','command':command,'timeout':4}]})
atomic(settings,d)
print('Live hook installed; backup='+str(backup))
