import json
from pathlib import Path
import tempfile
import unittest
from daily_workchat.forge_daily import Bank, scope

class DailyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root/'proof.txt'
        self.source.write_text('observed passing check')
        self.bank = Bank(self.root/'bank.sqlite3')
    def tearDown(self):
        self.bank.close(); self.temp.cleanup()
    def save(self, portable=False):
        return self.bank.remember('project-a','chat-a','release check',
            'Test the release in a fresh checkout',['release'],[str(self.source)],portable)
    def test_same_project_different_chats(self):
        self.save()
        result = self.bank.recall('project-a','chat-b','release')
        self.assertEqual(len(result['experiences']),1)
        self.assertFalse(result['authorizes_actions'])
    def test_project_separation(self):
        self.save()
        self.assertEqual(self.bank.recall('project-b','chat-b','release')['experiences'],[])
    def test_portable_workflow(self):
        self.save(True)
        self.assertEqual(len(self.bank.recall('project-b','chat-b','release')['experiences']),1)
    def test_changed_evidence_rejected(self):
        self.save(); self.source.write_text('changed')
        result = self.bank.recall('project-a','chat-b','release')
        self.assertEqual(result['experiences'],[])
        self.assertEqual(result['rejected'][0]['reason'],'evidence_changed_or_missing')
    def test_tampered_experience_rejected(self):
        item=self.save()
        item['lesson']='another lesson'
        with self.bank.db:
            self.bank.db.execute('UPDATE experiences SET payload=?',(json.dumps(item),))
        self.assertEqual(self.bank.recall('project-a','chat-b','release')['rejected'][0]['reason'],'integrity_mismatch')
    def test_no_unobserved_lesson(self):
        with self.assertRaises(ValueError):
            self.bank.remember('a','b','title','lesson',[],[])
    def test_credential_rejected(self):
        with self.assertRaises(ValueError):
            self.bank.remember('a','b','title','api_key=secret',[],[str(self.source)])
    def test_windows_and_wsl_project_scope_agree(self):
        self.assertEqual(scope('C:/projects/DemoRoot'),scope('/mnt/c/projects/DemoRoot'))
    def test_usage_for_every_chat(self):
        for chat in ('chat-a','chat-b','chat-c'):
            self.bank.recall('project-a',chat,'release')
        self.assertEqual(self.bank.status()['chat_count'],3)

if __name__=='__main__': unittest.main()


class InstallTests(unittest.TestCase):
    def test_preserves_settings_and_is_repeatable(self):
        from daily_workchat.install import install
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);home=root/'config';home.mkdir()
            (home/'AGENTS.md').write_text('Existing user preference\n')
            (home/'config.toml').write_text('model = "existing-model"\n')
            install(home,root/'skills');install(home,root/'skills')
            self.assertIn('Existing user preference',(home/'AGENTS.md').read_text())
            self.assertEqual((home/'AGENTS.md').read_text().count('<!-- experience-forge-daily:begin -->'),1)
            self.assertIn('existing-model',(home/'config.toml').read_text())
    def test_conflicting_server_is_not_overwritten(self):
        from daily_workchat.install import install
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);home=root/'config';home.mkdir()
            before='[mcp_servers.experience_forge_daily]\ncommand = "another-host"\n'
            (home/'config.toml').write_text(before)
            with self.assertRaises(ValueError): install(home,root/'skills')
            self.assertEqual((home/'config.toml').read_text(),before)
    def test_mcp_rejects_missing_evidence(self):
        from daily_workchat.mcp_server import call
        with self.assertRaises(ValueError):
            call('forge_remember',{'project':'demo','chat':'demo','title':'title','lesson':'lesson','evidence':[]})
