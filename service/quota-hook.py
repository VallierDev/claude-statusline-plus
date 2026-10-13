#!/usr/bin/env python3
"""Opt-in live quota reminders at natural tool boundaries; no model polling."""
import hashlib
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from quota import atomic, compact, fetch

STATE = Path.home()/'.cache/claude-quota/hook'

def handle(payload, now=None, state=STATE, reader=fetch):
    now=time.time() if now is None else now
    sid=payload.get('session_id')
    event=payload.get('hook_event_name')
    if not isinstance(sid,str) or not sid or len(sid)>256 or event not in ('PreToolUse','PostToolUse'):
        return None
    path=state/(hashlib.sha256(sid.encode()).hexdigest()+'.json')
    try: previous=json.loads(path.read_text())
    except (OSError,ValueError): previous={}
    if now-previous.get('checked_at',0)<60:
        return None
    data=reader(SimpleNamespace(session=sid,cwd=None,list=False))
    advice=data['sessions'][0]['advice'] if data.get('status')=='ok' else 'unknown'
    notify=not previous or advice!=previous.get('advice') or now-previous.get('notified_at',0)>=600
    record={'session_id':sid,'checked_at':now,'advice':advice,'notified_at':now if notify else previous.get('notified_at',0),'deliveries':previous.get('deliveries',0)+int(notify)}
    atomic(path,record)
    if not notify: return None
    context=('Quota checkpoint (user-requested): '+compact(data)+'. '
             'Working rule: >=80% used in either window means batch tools and avoid optional analysis; '
             '>=95% means finish a safe checkpoint, report reset time and defer discretionary work. '
             'Unknown is not full quota. Preserve current task; no model timer or repeated polling needed. '
             'Reported statusline data can be cached. This hook supplies the next checkpoint automatically; user can override advice.')
    return {'hookSpecificOutput':{'hookEventName':event,'additionalContext':context}}

if __name__=='__main__':
    try:
        result=handle(json.load(sys.stdin))
        if result: print(json.dumps(result,ensure_ascii=False))
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        pass  # Fail open: never interrupt production tools.
