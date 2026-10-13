import importlib.util
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('quota_hook',Path(__file__).with_name('quota-hook.py'));hook=importlib.util.module_from_spec(spec);spec.loader.exec_module(hook)
class HookTests(unittest.TestCase):
    def test_throttle_and_session_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp);calls=[]
            def read(args):
                calls.append(args.session);return {'status':'unknown','sessions':[]}
            p={'session_id':'a','hook_event_name':'PreToolUse'}
            self.assertIsNotNone(hook.handle(p,1000,state,read))
            self.assertIsNone(hook.handle(p,1010,state,read))
            self.assertIsNone(hook.handle(p,1061,state,read))
            self.assertIsNotNone(hook.handle(p,1601,state,read))
            self.assertEqual(calls,['a','a','a'])
            p['session_id']='b';self.assertIsNotNone(hook.handle(p,1602,state,read))
    def test_no_permission_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=hook.handle({'session_id':'a','hook_event_name':'PostToolUse'},1000,Path(tmp),lambda _: {'status':'unknown','sessions':[]})
            self.assertNotIn('permissionDecision',out['hookSpecificOutput'])
            self.assertNotIn('decision',out)
if __name__=='__main__':unittest.main()
