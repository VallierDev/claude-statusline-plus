#!/usr/bin/env python3
"""Private, session-scoped Claude Code statusline quota bridge. No credentials/API calls."""
import argparse
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import socket
import socketserver
import subprocess
import sys
import tempfile
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

ROOT = Path.home() / '.local/share/claude-quota'
STATE = Path.home() / '.cache/claude-quota'
SOCKET = (Path(os.environ.get('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')) / 'claude-quota.sock'
          if sys.platform == 'linux' else STATE / 'reader.sock')
TTL = 180


def atomic(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f, ensure_ascii=False, allow_nan=False)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def capture(payload, state=STATE, now=None):
    sid = payload.get('session_id')
    if not isinstance(sid, str) or not sid or len(sid) > 256:
        return
    windows = {}
    limits = payload.get('rate_limits')
    for key in ('five_hour', 'seven_day'):
        w = limits.get(key) if isinstance(limits, dict) else None
        used = w.get('used_percentage') if isinstance(w, dict) else None
        reset = w.get('resets_at') if isinstance(w, dict) else None
        windows[key] = {
            'used_percentage': used if number(used) and 0 <= used <= 100 else None,
            'resets_at': reset if number(reset) and reset > 0 else None,
        }
    cwd = payload.get('cwd') or (payload.get('workspace') or {}).get('current_dir')
    record = {'session_id': sid, 'cwd': cwd if isinstance(cwd, str) else None,
              'received_at': time.time() if now is None else now, 'windows': windows}
    atomic(state / (hashlib.sha256(sid.encode()).hexdigest() + '.json'), record)


def view(record, now):
    age = max(0, now - record['received_at'])
    result = {'session_id': record['session_id'], 'cwd': record.get('cwd'),
              'age_seconds': round(age), 'source': 'claude_code_statusline',
              'freshness': 'recently_received' if age <= TTL else 'stale', 'windows': {}}
    levels = []
    for key, w in record['windows'].items():
        used, reset = w.get('used_percentage'), w.get('resets_at')
        known = age <= TTL and number(used) and number(reset) and reset > now
        status = 'available' if known else ('stale' if age > TTL else 'unknown')
        remaining = round(100 - used, 2) if known else None
        level = 'stop' if known and used >= 95 else 'conserve' if known and used >= 80 else 'normal' if known else 'unknown'
        levels.append(level)
        result['windows'][key] = {'status': status, 'used_percentage': used,
            'remaining_percentage': remaining, 'resets_at': reset,
            'reset_in_seconds': max(0, round(reset-now)) if number(reset) else None}
    result['advice'] = 'stop' if 'stop' in levels else 'unknown' if 'unknown' in levels else 'conserve' if 'conserve' in levels else 'normal'
    return result


def query(sid=None, cwd=None, state=STATE, now=None):
    now = time.time() if now is None else now
    records = []
    for p in state.glob('*.json'):
        try:
            r = json.loads(p.read_text())
            if sid and r['session_id'] != sid:
                continue
            if cwd and r.get('cwd') != cwd:
                continue
            # Old sessions are retained for explicit lookup, excluded from discovery.
            if not sid and now-r['received_at'] > TTL:
                continue
            records.append(view(r, now))
        except (ValueError, KeyError, TypeError, OSError):
            continue
    records.sort(key=lambda r: r['age_seconds'])
    return {'status': 'ok' if len(records) == 1 else 'ambiguous' if records else 'unknown',
            'sessions': records, 'note': 'Reported percentages, not token counts. Timer refreshes may reuse Claude Code data; this service does not independently query Anthropic.'}


def compact(data):
    if data['status'] != 'ok':
        return f"quota={data['status']} sessions={len(data['sessions'])}; use --session ID (or --list); no balance assumed"
    r = data['sessions'][0]
    parts = []
    for key, label in (('five_hour', '5h'), ('seven_day', '7d')):
        w = r['windows'][key]
        parts.append(f"{label} remaining={w['remaining_percentage']}% reset_in={w['reset_in_seconds']}s" if w['status']=='available' else f"{label}={w['status']}")
    return '; '.join(parts + [f"advice={r['advice']}", f"received_age={r['age_seconds']}s (reported data)"])


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/health':
            data = {'status': 'ok'}
        elif url.path == '/v1/quota':
            args = parse_qs(url.query)
            data = query(args.get('session', [None])[0], args.get('cwd', [None])[0])
        else:
            self.send_error(404)
            return
        body = json.dumps(data, allow_nan=False).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def serve():
    os.umask(0o077)
    SOCKET.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    SOCKET.unlink(missing_ok=True)
    with Server(str(SOCKET), Handler) as server:
        os.chmod(SOCKET, 0o600)
        try:
            server.serve_forever()
        finally:
            SOCKET.unlink(missing_ok=True)


class Connection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(3)
        self.sock.connect(str(SOCKET))


def fetch(args):
    from urllib.parse import urlencode
    params = {k:v for k,v in {'session': args.session, 'cwd': None if args.list else args.cwd}.items() if v}
    conn = Connection('localhost', timeout=3)
    try:
        conn.request('GET', '/v1/quota?' + urlencode(params))
        return json.loads(conn.getresponse().read())
    except (OSError, ValueError, http.client.HTTPException):
        return {'status': 'service_unavailable', 'sessions': []}
    finally:
        conn.close()


def main():
    if len(sys.argv)>1 and sys.argv[1]=='serve':
        serve()
        return
    if len(sys.argv)>1 and sys.argv[1]=='capture-render':
        raw = sys.stdin.buffer.read()
        try:
            capture(json.loads(raw))
        except (ValueError, TypeError, AttributeError, OSError):
            pass  # Publishing must never break the existing statusline.
        cfg = json.loads((ROOT/'renderer.json').read_text())
        raise SystemExit(subprocess.run(cfg['command'], shell=True, input=raw).returncode)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', default=os.environ.get('CLAUDE_SESSION_ID') or os.environ.get('CLAUDE_CODE_SESSION_ID'))
    parser.add_argument('--cwd')
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--compact', action='store_true')
    parser.add_argument('--watch', action='store_true', help='poll locally without calling any model; Ctrl-C to stop')
    parser.add_argument('--interval', type=int, default=60)
    args = parser.parse_args()
    last = None
    while True:
        data = fetch(args)
        # Watch reports semantic changes, not a new model conversation.
        comparison = json.loads(json.dumps(data))
        for r in comparison['sessions']:
            r.pop('age_seconds', None)
            for w in r['windows'].values():
                w.pop('reset_in_seconds', None)
        stable = json.dumps(comparison, sort_keys=True)
        if not args.watch or stable != last:
            print(compact(data) if args.compact else json.dumps(data, ensure_ascii=False), flush=True)
        last = stable
        if not args.watch:
            return
        time.sleep(max(10, args.interval))


if __name__ == '__main__':
    main()
