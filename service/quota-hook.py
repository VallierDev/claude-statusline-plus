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
    session = data['sessions'][0] if data.get('status') == 'ok' else {}
    cache = session.get('prompt_cache') or {}
    expiry = cache.get('expires_at')
    due = (cache.get('status') == 'warm' and isinstance(cache.get('remaining_seconds'), (int,float))
           and 0 < cache['remaining_seconds'] <= 300 and advice in ('normal','conserve')
           and previous.get('keepalive_expiry') != expiry)
    notify=due or not previous or advice!=previous.get('advice') or now-previous.get('notified_at',0)>=600
    record={'session_id':sid,'checked_at':now,'advice':advice,'notified_at':now if notify else previous.get('notified_at',0),'deliveries':previous.get('deliveries',0)+int(notify)}
    record['keepalive_expiry'] = expiry if due else previous.get('keepalive_expiry')
    atomic(path,record)
    if not notify: return None
    context = 'Quota/cache checkpoint: '+compact(data)+'. Advice weighs usage against time to reset: conserve only at >=80% used AND remaining quota share < remaining time share; stop likewise at >=95%. Unknown is not full quota. No duplicate polling.'
    if due:
        context += (' Cache expires within 5 minutes. At the next normal response, give one very short progress checkpoint (at most one sentence: completed/current/next), then continue under quota rules. '
                    'Reuse this same session; no new agent, repeated keepalive, unrelated tool, or extra model timer. An actual cache-hit model request may refresh cache; local queries do not. Do not interrupt a running tool.')
    return {'hookSpecificOutput':{'hookEventName':event,'additionalContext':context}}

if __name__=='__main__':
    try:
        result=handle(json.load(sys.stdin))
        if result: print(json.dumps(result,ensure_ascii=False))
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        pass  # Fail open: never interrupt production tools.
