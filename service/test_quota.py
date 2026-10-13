import json
import tempfile
import unittest
from pathlib import Path
from quota import capture, query, compact

class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.state = Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()
    def emit(self, sid='one', limits=None, at=1000):
        capture({'session_id': sid, 'cwd': '/work', 'rate_limits': limits}, self.state, at)
    def limits(self, used=30):
        return {k:{'used_percentage':used,'resets_at':2000} for k in ('five_hour','seven_day')}
    def test_known_and_permissions(self):
        self.emit(limits=self.limits())
        result=query('one',state=self.state,now=1010)
        self.assertEqual(result['sessions'][0]['windows']['five_hour']['remaining_percentage'],70)
        self.assertEqual(next(self.state.iterdir()).stat().st_mode & 0o777,0o600)
    def test_missing_overwrites_previous(self):
        self.emit(limits=self.limits()); self.emit()
        self.assertIn('5h=unknown',compact(query('one',state=self.state,now=1010)))
    def test_invalid_values(self):
        self.emit(limits={'five_hour': {'used_percentage':True,'resets_at':2000}})
        self.assertIsNone(query('one',state=self.state,now=1010)['sessions'][0]['windows']['five_hour']['remaining_percentage'])
    def test_stale_and_expired_never_reset_to_full(self):
        self.emit(limits=self.limits())
        for now in (1200,2001):
            result=query('one',state=self.state,now=now)
            self.assertIsNone(result['sessions'][0]['windows']['five_hour']['remaining_percentage'])
        self.emit(limits=self.limits(),at=2001)
        self.assertEqual(query('one',state=self.state,now=2002)['sessions'][0]['advice'],'unknown')
    def test_sessions_not_merged(self):
        self.emit('one', self.limits(10)); self.emit('two', self.limits(95))
        self.assertEqual(query(cwd='/work',state=self.state,now=1010)['status'],'ambiguous')
        self.assertEqual(query('two',state=self.state,now=1010)['sessions'][0]['advice'],'stop')
    def test_only_whitelist_persisted(self):
        capture({'session_id':'one','cwd':'/work','api_key':'secret','transcript':'private'},self.state,1000)
        raw=next(self.state.iterdir()).read_text()
        self.assertNotIn('secret',raw);self.assertNotIn('private',raw)
    def test_no_session_no_data(self):
        capture({'rate_limits':self.limits()},self.state,1000)
        self.assertEqual(query(state=self.state,now=1010)['status'],'unknown')

class SocketTests(unittest.TestCase):
    def test_private_socket_http_contract(self):
        import quota
        import threading
        with tempfile.TemporaryDirectory() as tmp:
            original_socket, original_state = quota.SOCKET, quota.STATE
            quota.SOCKET = Path(tmp)/'reader.sock'
            # Handler uses query's default STATE; inject an isolated query instead.
            original_query = quota.query
            quota.query = lambda sid=None,cwd=None: original_query(sid,cwd,Path(tmp)/'state')
            try:
                with quota.Server(str(quota.SOCKET),quota.Handler) as server:
                    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
                    conn=quota.Connection('localhost')
                    conn.request('GET','/health')
                    self.assertEqual(json.loads(conn.getresponse().read()),{'status':'ok'})
                    conn.close()
                    conn=quota.Connection('localhost')
                    conn.request('GET','/v1/quota?session=missing')
                    self.assertEqual(json.loads(conn.getresponse().read())['status'],'unknown')
                    conn.close()
                    server.shutdown();thread.join()
            finally:
                quota.SOCKET,quota.STATE,quota.query=original_socket,original_state,original_query

class InstallerTests(unittest.TestCase):
    def test_install_and_update_preserve_renderer_and_other_settings(self):
        import runpy
        import subprocess
        from unittest.mock import patch
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);(home/'.claude').mkdir()
            settings=home/'.claude/settings.json'
            initial={'model':'keep-me','hooks':{'custom':[]},'statusLine':{'type':'command','command':'echo original','padding':2}}
            settings.write_text(json.dumps(initial))
            instructions=home/'.claude/CLAUDE.md';instructions.write_text('Preserve this instruction.\n')
            for _ in range(2):
                with patch('pathlib.Path.home',return_value=home),patch('subprocess.run'),contextlib.redirect_stdout(io.StringIO()):
                    runpy.run_path(str(Path(__file__).with_name('install.py')),run_name='__main__')
            current=json.loads(settings.read_text())
            self.assertEqual(current['model'],initial['model'])
            self.assertEqual(current['hooks'],initial['hooks'])
            self.assertEqual(current['statusLine']['padding'],2)
            self.assertEqual(json.loads((home/'.local/share/claude-quota/renderer.json').read_text())['command'],'echo original')
            self.assertTrue(instructions.read_text().startswith('Preserve this instruction.'))
            self.assertEqual(instructions.read_text().count('<!-- claude-quota-service -->'),1)

if __name__ == '__main__':
    unittest.main()
