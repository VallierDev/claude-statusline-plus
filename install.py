#!/usr/bin/env python3
"""Install locally, preserving account, model and permission settings."""
import json
import os
from pathlib import Path
import shutil
import tempfile
from datetime import datetime, timezone


def atomic_write(path, content, mode=0o600):
    fd, temporary = tempfile.mkstemp(prefix=".statusline-plus-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def install(home=None):
    if not shutil.which("jq") or not shutil.which("bash"):
        raise ValueError("Install bash and jq first.")
    root = (Path(home) if home else Path.home()) / ".claude"
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    settings = root / "settings.json"
    original = settings.read_text() if settings.exists() else "{}"
    data = json.loads(original)
    if not isinstance(data, dict):
        raise ValueError("settings.json must contain a JSON object; nothing changed.")
    target = root / "claude-statusline-plus.sh"
    backup_root = root / "backups" / "claude-statusline-plus"
    backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup_root.chmod(0o700)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = backup_root / stamp
    backup.mkdir(mode=0o700)
    if settings.exists():
        atomic_write(backup / "settings.json", original)
    if target.exists():
        atomic_write(backup / "claude-statusline-plus.sh", target.read_text(), 0o700)
    # Keep a record of just the previous statusLine for a selective rollback.
    atomic_write(backup / "previous-statusline.json", json.dumps({
        "present": "statusLine" in data, "value": data.get("statusLine")
    }, indent=2) + "\n")
    import shlex
    data["statusLine"] = {
        "type": "command", "command": shlex.quote(str(target)), "refreshInterval": 60
    }
    source = Path(__file__).with_name("claude-pace.sh").read_text()
    atomic_write(target, source, 0o700)
    atomic_write(settings, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"Installed: {target}\nBackup: {backup}\nStart a new Claude Code session.")
    return backup


if __name__ == "__main__":
    try:
        install()
    except (ValueError, OSError) as exc:
        raise SystemExit(str(exc))
