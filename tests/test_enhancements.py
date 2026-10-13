import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StatuslineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="statusline-plus-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.env = dict(os.environ, HOME=str(self.home), XDG_RUNTIME_DIR="")
        self.project = self.home / "project with spaces"
        self.project.mkdir()

    def render(self, payload):
        raw = payload if isinstance(payload, str) else json.dumps(payload)
        result = subprocess.run(["bash", str(ROOT / "claude-pace.sh")], input=raw,
                                text=True, capture_output=True, env=self.env, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        return re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)

    def payload(self):
        now = int(time.time())
        return {"model": {"display_name": "Opus"},
                "workspace": {"project_dir": str(self.project)},
                "context_window": {"used_percentage": 10, "context_window_size": 200000},
                "rate_limits": {"five_hour": {"used_percentage": 25, "resets_at": now + 18000},
                                "seven_day": {"used_percentage": 40, "resets_at": now + 604800}}}

    def test_quota_and_cache_are_separate(self):
        payload = self.payload()
        payload["prompt_cache"] = {"expires_at": int(time.time()) + 120, "ttl": "5m"}
        out = self.render(payload)
        self.assertIn("5h 25%", out)
        self.assertIn("7d 40%", out)
        self.assertRegex(out, r"cache")
        self.assertNotIn("cache --", out)

    def test_tool_events_do_not_reset_last_model_activity(self):
        payload = self.payload()
        payload["session_id"] = "synthetic-session"
        encoded = "-" + str(self.project).lstrip("/").replace("/", "-")
        folder = self.home / ".claude/projects" / encoded
        folder.mkdir(parents=True)
        from datetime import datetime, timezone
        old = datetime.fromtimestamp(time.time() - 600, timezone.utc).isoformat().replace("+00:00", "Z")
        new = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        rows = [{"type": "assistant", "timestamp": old, "message": {"usage": {"input_tokens": 1}}},
                {"type": "user", "timestamp": new, "message": {"content": "synthetic tool result"}}]
        (folder / "synthetic-session.jsonl").write_text("\n".join(map(json.dumps, rows)) + "\n")
        self.assertIn("last 10m", self.render(payload))

    def test_invalid_json_and_nonobject_input_fail_gently(self):
        for data in ["broken", "null", "[]"]:
            with self.subTest(data=data):
                self.assertEqual(self.render(data), "Claude [invalid session data]\n")

    def test_current_dir_and_missing_quota(self):
        payload = self.payload()
        payload["workspace"] = {"current_dir": str(self.project)}
        payload.pop("rate_limits")
        out = self.render(payload)
        self.assertIn("project with spaces", out)
        self.assertIn("5h --", out)
        self.assertIn("7d --", out)

    def test_nonobject_settings_do_not_break_display(self):
        folder = self.home / ".claude"
        folder.mkdir()
        (folder / "settings.json").write_text("[]")
        self.assertIn("5h 25%", self.render(self.payload()))


class InstallerTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("installer", ROOT / "install.py")
        self.installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.installer)
        self.tmp = tempfile.TemporaryDirectory(prefix="statusline-install-")
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "home with spaces"
        (self.home / ".claude").mkdir(parents=True)

    def test_install_preserves_unrelated_settings_and_backup(self):
        old = {"model": "opus", "permissions": {"defaultMode": "default"},
               "env": {"SYNTHETIC_SETTING": "unchanged"}, "statusLine": {"command": "old-command"}}
        settings = self.home / ".claude/settings.json"
        settings.write_text(json.dumps(old))
        backup = self.installer.install(self.home)
        new = json.loads(settings.read_text())
        for key in ["model", "permissions", "env"]:
            self.assertEqual(new[key], old[key])
        self.assertEqual(json.loads((backup / "settings.json").read_text()), old)
        self.assertEqual(settings.stat().st_mode & 0o777, 0o600)
        self.assertIn("'", new["statusLine"]["command"])

    def test_invalid_settings_are_left_untouched(self):
        p = self.home / ".claude/settings.json"
        p.write_text("invalid")
        with self.assertRaises(ValueError):
            self.installer.install(self.home)
        self.assertEqual(p.read_text(), "invalid")
        self.assertFalse((p.parent / "claude-statusline-plus.sh").exists())


if __name__ == "__main__":
    unittest.main()
