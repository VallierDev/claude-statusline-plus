#!/usr/bin/env python3
"""Restore only the quota-related changes from a specified installation backup."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from quota import atomic

backup=Path(sys.argv[1]).expanduser()
manifest=json.loads((backup/'manifest.json').read_text())
home=Path.home()
linux=sys.platform=='linux'
unit=home/('.config/systemd/user/claude-quota.service' if linux else 'Library/LaunchAgents/com.vallierdev.claude-quota.plist')
if linux:
    subprocess.run(['systemctl','--user','disable','--now','claude-quota.service'],check=False)
else:
    subprocess.run(['launchctl','bootout',f'gui/{os.getuid()}',str(unit)],check=False)
for item in manifest:
    p=Path(item['path']); old=Path(item['backup'])
    if p==home/'.claude/settings.json':
        current=json.loads(p.read_text())
        previous=json.loads(old.read_text()) if item['present'] else {}
        if 'statusLine' in previous: current['statusLine']=previous['statusLine']
        else: current.pop('statusLine',None)
        atomic(p,current)
    elif p==home/'.claude/CLAUDE.md':
        if p.exists():
            text=p.read_text(); start=text.find('<!-- claude-quota-service -->'); end=text.find('<!-- /claude-quota-service -->')
            if start>=0 and end>=start:
                previous=old.read_text() if item['present'] else ''
                old_start=previous.find('<!-- claude-quota-service -->')
                old_end=previous.find('<!-- /claude-quota-service -->')
                block=previous[old_start:old_end+len('<!-- /claude-quota-service -->')] if old_start>=0 and old_end>=old_start else ''
                text=text[:start]+block+text[end+len('<!-- /claude-quota-service -->'):]
                p.write_text(text)
    elif item['present']:
        shutil.copy2(old,p);p.chmod(item.get('mode',0o600))
    else:
        p.unlink(missing_ok=True)
if unit.exists():
    if linux:
        subprocess.run(['systemctl','--user','daemon-reload'],check=True)
        subprocess.run(['systemctl','--user','enable','--now','claude-quota.service'],check=True)
    else:
        subprocess.run(['launchctl','bootstrap',f'gui/{os.getuid()}',str(unit)],check=True)
print('Quota service restored. Plugin is separate: claude plugin uninstall pace-statusline-plus@pace-statusline-plus-local')
