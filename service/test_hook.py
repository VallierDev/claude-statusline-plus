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
    def test_keepalive_once_per_expiry_and_quota_priority(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp);payload={'session_id':'a','hook_event_name':'PreToolUse'}
            data={'status':'ok','sessions':[{'advice':'normal','age_seconds':0,'windows':{k:{'status':'available','remaining_percentage':70,'reset_in_seconds':3600} for k in ('five_hour','seven_day')},'prompt_cache':{'status':'warm','expires_at':2000,'remaining_seconds':400}}]}
            read=lambda _:data
            hook.handle(payload,1000,state,read)
            data['sessions'][0]['prompt_cache']['remaining_seconds']=250
            self.assertIn('progress checkpoint',hook.handle(payload,1061,state,read)['hookSpecificOutput']['additionalContext'])
            self.assertIsNone(hook.handle(payload,1122,state,read))
            data['sessions'][0]['prompt_cache']['expires_at']=3000
            self.assertIn('progress checkpoint',hook.handle(payload,1183,state,read)['hookSpecificOutput']['additionalContext'])
            for advice in ('stop','unknown'):
                data['sessions'][0]['advice']=advice
                data['sessions'][0]['prompt_cache']['expires_at']+=1000
                output=hook.handle(payload,1244 if advice=='stop' else 1305,state,read)
                self.assertNotIn('progress checkpoint',output['hookSpecificOutput']['additionalContext'])

    def test_keepalive_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg=Path(tmp)/'k.json'
            self.assertIsNone(hook.keepalive_context(cfg))
            cfg.write_text('{"enabled":true}')
            c=hook.keepalive_context(cfg)
            self.assertIn('CronCreate',c);self.assertIn('3,53 * * * *',c)
            cfg.write_text('{"enabled":false}');self.assertIsNone(hook.keepalive_context(cfg))
            self.assertIsNone(hook.handle({'session_id':'a','hook_event_name':'SessionStart'},1000,Path(tmp),lambda _:{}) if not hook.CONFIG.exists() else None)

if __name__=='__main__':unittest.main()
