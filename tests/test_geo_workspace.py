import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from am_seo.geo_workspace import GeoWorkspace, robots_allows, traffic_report, read_public
from am_seo.geo_pages import page_files


class GeoWorkspaceTests(unittest.TestCase):
    def test_generated_question_gets_its_own_researched_page_not_an_unrelated_template(self):
        question = {**self.playbook['questions'][0], 'id':'P-fixture-Q01','basis':'skill_generated', 'prompt':'How should I place a wireless gaming mouse receiver?', 'intent':'how'}
        self.workspace.adopt_questions([question], 'P-fixture')
        self.workspace.generate([question['id']])
        calls=[]
        def runner(prompt,schema,directory,search):
            calls.append((prompt,search))
            return {'result':{'answer':'Check the receiver placement in your own setup.','steps':['Move the receiver away from obstructions.'],'checks':[{'label':'Is there a clear path?','yes':'Test the connection.','no':'Try an unobstructed position.'},{'label':'Can you compare two positions?','yes':'Record the result.','no':'Keep the setup unchanged until you can test.'}],'limitations':['No latency or range guarantee.'],'sources':[{'url':'https://support.logi.com/','title':'Official support'}]},'trace':{'web_search_events':[{'type':'search','query':'fixture receiver setup'}]}}
        self.workspace.page_runner=runner
        task=self.workspace.prepare('page-'+question['id'])
        page=self.workspace.artifact(task['id'],'index.html').decode()
        self.assertIn(question['prompt'],page)
        self.assertIn('Is there a clear path?',page)
        self.assertNotIn('battery rotation',page.lower())
        self.assertTrue(calls[0][1])
        self.assertEqual(task['completion_scope'],'local_artifact_not_published')
        self.assertNotIn('check_status',task)

    def test_dynamic_page_requires_actual_research_trace_before_prepared(self):
        question={**self.playbook['questions'][0],'id':'P-fixture-Q01','basis':'skill_generated'}
        self.workspace.adopt_questions([question],'P-fixture');self.workspace.generate([question['id']])
        self.workspace.page_runner=lambda *args,**kwargs:{'result':{},'trace':{}}
        with self.assertRaises(ValueError):self.workspace.prepare('page-'+question['id'])
        self.assertEqual(self.workspace.task('page-'+question['id'])['status'],'ready')

    def test_checkbox_is_persisted_without_overwriting_verification_or_claiming_publication(self):
        self.generate()
        self.workspace.check('ai-crawlers')
        before = self.workspace.task('ai-crawlers')['verification']
        self.workspace.toggle('ai-crawlers', True)
        restored = GeoWorkspace(self.root)
        task = next(t for t in restored.state()['tasks'] if t['id'] == 'ai-crawlers')
        self.assertTrue(task['execution_done'])
        self.assertEqual(task['validation_status'], 'passed')
        self.assertEqual(task['verification'], before)
        self.assertEqual(task['status'], 'ready')
        self.assertEqual(task['group'], 'foundation')
        restored.toggle('ai-crawlers', False)
        self.assertFalse(restored.task('ai-crawlers')['execution_done'])
        with self.assertRaises(ValueError): restored.toggle('ai-crawlers', 'yes')

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='am-geo-focus-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'config').mkdir()
        self.playbook = json.loads((ROOT / 'config/geo-playbook.json').read_text())
        (self.root / 'config/geo-playbook.json').write_text(json.dumps(self.playbook))
        self.calls = []
        def fetch(url):
            self.calls.append(url)
            return {'url': url, 'final_url': url, 'status': 200, 'captured_at': '2026-11-04T00:00:00+00:00',
                    'body': 'User-agent: *\nDisallow: /admin\n', 'sha256': 'fixture', 'content_type': 'text/plain'}
        self.workspace = GeoWorkspace(self.root, fetcher=fetch)

    def generate(self):
        selected = [q['id'] for q in self.playbook['questions'] if q['selected']]
        return self.workspace.generate(selected)

    def test_questions_have_four_intents_bilingual_targets_and_no_measured_volume(self):
        questions = self.playbook['questions']
        self.assertEqual({q['intent'] for q in questions}, {'find', 'how', 'alternatives', 'facts'})
        self.assertEqual(len({q['path'] for q in questions}), len(questions))
        self.assertTrue(all(q['validation_status'] == 'candidate_not_search_volume' for q in questions))
        for intent in ('find', 'how', 'alternatives', 'facts'):
            self.assertEqual({q['locale'] for q in questions if q['intent'] == intent}, {'zh-CN', 'en-US'})

    def test_generate_idempotent_prepare_and_restart_preserve_real_artifacts(self):
        generated = self.generate()
        self.assertEqual(len(generated['tasks']), 12)
        self.generate()
        self.assertEqual(len(self.workspace.state()['tasks']), 12)
        task = self.workspace.prepare('page-' + self.playbook['questions'][0]['id'])
        self.assertEqual(task['status'], 'prepared')
        self.assertEqual(task['completion_scope'], 'local_artifact_not_published')
        self.assertEqual(self.calls, [])
        page = self.workspace.artifact(task['id'], 'index.html').decode()
        self.assertIn('id="tool"', page)
        self.assertIn('noindex', page)
        self.assertIn(self.playbook['questions'][0]['prompt'], page)
        restored = GeoWorkspace(self.root)
        self.assertEqual(restored.artifact(task['id'], 'index.html'), page.encode())
        path = self.root / task['artifacts'][0]['path']
        path.write_text('tampered')
        with self.assertRaises(ValueError): restored.artifact(task['id'], 'index.html')
        with self.assertRaises(ValueError): restored.artifact(task['id'], '../../config/project.json')

    def test_invalid_selection_fails_without_network_or_writes(self):
        for selection in ([], ['invalid'], [self.playbook['questions'][0]['id']] * 2, None):
            with self.assertRaises(ValueError): self.workspace.generate(selection)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.workspace.path.exists())

    def test_rule_checks_keep_raw_evidence_and_dont_claim_published_or_bot_access(self):
        self.generate()
        result = self.workspace.check('ai-crawlers')
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(result['check_status'], 'passed')
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['verification']['scope'], 'public_rule_or_html_diagnostic_only')
        for record in result['verification']['evidence']:
            self.assertTrue((self.root / record['path']).is_file())
        self.workspace.check('ai-crawlers')
        self.assertEqual(len(self.workspace.state()['history']), 1)

    def test_html_error_page_cannot_count_as_robots(self):
        self.generate()
        self.workspace.fetcher = lambda url: {'url': url, 'status': 200, 'body': '<html>error</html>', 'content_type': 'text/html'}
        result = self.workspace.check('ai-crawlers')
        self.assertEqual(result['check_status'], 'needs_work')
        self.assertFalse(any('OAI-SearchBot' in c['title'] for c in result['checks']))

    def test_fetch_errors_are_recorded_as_errors(self):
        self.generate()
        def fail(url): raise OSError('fixture unavailable')
        self.workspace.fetcher = fail
        result = self.workspace.check('answer-schema')
        self.assertTrue(result['checks'][0]['error'])
        self.assertEqual(result['check_status'], 'needs_work')

    def test_draft_noindex_cannot_pass_online_page_check(self):
        self.generate()
        task = self.workspace.task('page-' + self.playbook['questions'][0]['id'])
        files = page_files(task['question'], task['target_url'])
        self.workspace.fetcher = lambda url: {'url': url, 'status': 200, 'body': files['index.html']}
        result = self.workspace.check(task['id'])
        self.assertFalse(next(c for c in result['checks'] if c['title'] == '未发现页面显式 noindex')['passed'])
        self.assertEqual(result['check_status'], 'needs_work')

    def test_public_fetch_rejects_unrelated_private_or_credential_urls_before_network(self):
        for url in ('http://127.0.0.1/', 'https://angrymiao.com.evil.test/', 'https://user:secret@store.angrymiao.com/', 'https://www.angrymiao.com:444/'):
            with self.assertRaises(ValueError): read_public(url)

    def test_robots_specific_groups_longest_match_private_paths_and_allow_ties(self):
        body = 'User-agent: *\nDisallow: /private\nDisallow: /products/\nAllow: /products/public$\nUser-agent: OAI-SearchBot\nDisallow: /\nAllow: /products/public$\nUser-agent: OAI-SearchBot\nAllow: /en/tools/\n'
        self.assertTrue(robots_allows(body, 'OAI-SearchBot', '/products/public'))
        self.assertFalse(robots_allows(body, 'OAI-SearchBot', '/products/public/secret'))
        self.assertTrue(robots_allows(body, 'OAI-SearchBot', '/en/tools/selector/'))
        self.assertFalse(robots_allows(body, 'OAI-SearchBot', '/private'))
        self.assertFalse(robots_allows(body, 'PerplexityBot', '/private'))
        self.assertTrue(robots_allows('User-agent: *\nDisallow: /x\nAllow: /x', 'bot', '/x'))

    def test_traffic_exact_hosts_native_channel_and_non_ai_do_not_mix(self):
        text = 'Session source / medium,Sessions,Key events\nchatgpt.com / ai-assistant,5,1\nperplexity.ai / referral,3,2\nchatgpt.com.evil.test / referral,50,10\ngoogle / organic,100,20\n(direct) / (none),20,0\nnew-assistant / ai-assistant,2,0\n'
        report = traffic_report(text, '2026-11-01', '2026-11-03', 'store.angrymiao.com')
        self.assertEqual(report['ai_sessions'], 10)
        self.assertEqual(report['ai_key_events'], 3)
        self.assertEqual(report['report_sessions'], 180)
        self.assertNotIn('csv', report)
        self.assertNotIn('user_id', report)

    def test_traffic_missing_data_stays_null_zero_report_is_real_import_only(self):
        self.assertIsNone(self.workspace.state()['traffic'])
        payload = {'csv': 'source,sessions\ngoogle,0\n', 'start_date': '2026-11-01', 'end_date': '2026-11-03', 'property_host': 'store.angrymiao.com'}
        self.workspace.import_traffic(payload)
        self.assertEqual(self.workspace.state()['traffic']['ai_sessions'], 0)
        self.assertIsNone(self.workspace.state()['traffic']['ai_key_events'])
        self.workspace.import_traffic(payload)
        self.assertEqual(self.workspace.state()['traffic']['ai_sessions'], 0)
        self.assertEqual(len(self.workspace.state()['history']), 1)

    def test_traffic_rejects_personal_columns_bad_dates_counts_duplicates_and_ambiguous_fields(self):
        invalid = ['source,sessions,email\nchatgpt.com,2,a@b.com\n', 'source,sessions\nhttps://chatgpt.com/?token=secret,2\n', 'source,sessions\nchatgpt.com,-1\n', 'source,sessions\nchatgpt.com,1.5\n', 'source,sessions,key_events\nchatgpt.com,1,NaN\n', 'source,sessions\nchatgpt.com,1\nchatgpt.com,2\n', 'source,Session source / medium,sessions\nchatgpt.com,google / organic,3\n']
        for csv in invalid:
            with self.assertRaises(ValueError): traffic_report(csv, '2026-11-01', '2026-11-03', 'store.angrymiao.com')
        for start, end, host in [('bad', '2026-11-01', 'store.angrymiao.com'), ('2026-11-04', '2026-11-01', 'store.angrymiao.com'), ('2026-11-01', '2026-11-03', 'other.test')]:
            with self.assertRaises(ValueError): traffic_report('source,sessions\nchatgpt.com,1', start, end, host)


if __name__ == '__main__': unittest.main()
