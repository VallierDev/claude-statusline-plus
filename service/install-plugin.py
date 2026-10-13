#!/usr/bin/env python3
"""Install/update this exact checkout as a local plugin (no GitHub tag dependency)."""
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
home=Path.home()
source=Path(__file__).resolve().parent.parent
market=home/'.local/share/claude-quota-marketplace'
plugin=market/'plugins/pace-statusline-plus'
backup=home/'.claude/backups/claude-quota-plugin'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
backup.mkdir(mode=0o700,parents=True)
for name,path in [('settings.json',home/'.claude/settings.json'),('installed_plugins.json',home/'.claude/plugins/installed_plugins.json'),('known_marketplaces.json',home/'.claude/plugins/known_marketplaces.json')]:
    if path.exists():
        shutil.copy2(path,backup/name)
        (backup/name).chmod(0o600)
if plugin.exists():
    shutil.copytree(plugin,backup/'plugin')
    shutil.rmtree(plugin)
plugin.parent.mkdir(parents=True,exist_ok=True)
shutil.copytree(source,plugin,ignore=shutil.ignore_patterns('__pycache__','.git'))
meta=market/'.claude-plugin'; meta.mkdir(exist_ok=True)
(meta/'marketplace.json').write_text(json.dumps({'name':'pace-statusline-plus-local','owner':{'name':'VallierDev'},'plugins':[{'name':'pace-statusline-plus','source':'./plugins/pace-statusline-plus','description':'Local quota command and existing statusline'}]},indent=2)+'\n')
subprocess.run(['claude','plugin','marketplace','add',str(market)],check=True)
# Update an existing installed plugin after publishing the local marketplace.
p=home/'.claude/plugins/installed_plugins.json'
installed=json.loads(p.read_text()).get('plugins',{}) if p.exists() else {}
name='pace-statusline-plus@pace-statusline-plus-local'
if name in installed:
    subprocess.run(['claude','plugin','update',name],check=True)
    # A local checkout can change without a version bump during development.
    # Reinstall only our user-scoped plugin if its cached command is outdated.
    entries=json.loads(p.read_text()).get('plugins',{}).get(name,[])
    wanted=(source/'commands/quota.md').read_bytes()
    stale=any(e.get('scope')=='user' and (not (Path(e['installPath'])/'commands/quota.md').exists() or (Path(e['installPath'])/'commands/quota.md').read_bytes()!=wanted) for e in entries)
    if stale:
        subprocess.run(['claude','plugin','uninstall',name,'--scope','user'],check=True)
        subprocess.run(['claude','plugin','install',name,'--scope','user'],check=True)
else:
    subprocess.run(['claude','plugin','install',name,'--scope','user'],check=True)
print('Plugin backup='+str(backup))
