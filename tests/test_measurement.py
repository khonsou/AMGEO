"""Real measurement rules; all observations in these tests are temporary fixtures."""
import json
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from am_seo.measurement import answer_panel, diagnose_html, measure, summarize_answers, technical_panel


class MeasurementTests(unittest.TestCase):
    def core_plan(self):
        return json.loads((ROOT / 'config/answer-panel.json').read_text())

    def test_core_panel_samples_both_product_lines_without_brand_context_or_old_seed_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seeds = root / 'outputs/agent-kit/query-seeds.json'
            seeds.parent.mkdir(parents=True)
            original = b'{"queries": [{"id":"EN-M-02","language":"en-US","prompt":"Legacy neutral question?"}]}\n'
            seeds.write_bytes(original)
            (root / 'AGENTS.md').write_text('BRAND CONTEXT MUST NOT ENTER MEASUREMENT')
            calls = []
            def factory(cwd):
                self.assertFalse((cwd / 'AGENTS.md').exists())
                def run(prompt, schema, directory, search=True):
                    self.assertNotIn('BRAND CONTEXT', prompt)
                    self.assertNotIn('Angry Miao', prompt)
                    self.assertNotIn('怒喵', prompt)
                    self.assertNotIn('CYBERBOARD', prompt)
                    calls.append((prompt, directory.name))
                    return {'result': {'status': 'completed', 'answer_text': 'A neutral product answer.', 'citations': []},
                            'trace': {'cli_version': 'fixture-cli', 'web_search_events': [{'query': 'fixture query'}]}}
                return run
            plan = self.core_plan()
            result = answer_panel(root, {'id': 'C-core', 'market': 'both'}, root / 'core', factory, panel_plan=plan)
            self.assertEqual({name for _, name in calls}, {q['id'] for q in plan['queries']})
            self.assertEqual(len(calls), 4)
            self.assertEqual(result['panel_version'], 'core-discovery-answer-v1')
            self.assertEqual(result['panel_title'], plan['title'])
            self.assertEqual(result['topic_coverage'], {'en-US': ['ai_device', 'mouse'], 'zh-CN': ['ai_device', 'mouse']})
            self.assertEqual({record['product_line'] for record in result['observations']}, {'mouse', 'ai_device'})
            self.assertEqual({g['successful_tests'] for g in result['groups']}, {2})
            self.assertEqual(seeds.read_bytes(), original)
            self.assertEqual(json.loads((root / 'core/panel-plan.json').read_text()), plan)
            self.assertEqual(result['panel_plan_sha256'], result['protocol']['panel_plan_sha256'])
            self.assertIn('不可比较', result['baseline_rule'])
            # Merely having the new panel does not change direct legacy runs.
            calls.clear()
            legacy = answer_panel(root, {'id': 'C-legacy', 'market': 'en-US'}, root / 'legacy', factory)
            self.assertEqual(legacy['panel_version'], 'bilingual-discovery-pilot-v1')
            self.assertEqual([name for _, name in calls], ['EN-M-02'])

    def test_core_panel_fingerprint_changes_with_question_and_market_and_keeps_errors_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            def factory(cwd):
                def run(prompt, schema, directory, search=True):
                    if directory.name == 'CORE-EN-M01':
                        raise OSError('fixture provider failure')
                    return {'result': {'status': 'no_ai_answer', 'answer_text': '', 'citations': []},
                            'trace': {'cli_version': 'fixture-cli', 'web_search_events': [{'query': 'fixture query'}]}}
                return run
            plan = self.core_plan()
            result = answer_panel(root, {'id': 'C-fixture', 'market': 'en-US'}, root / 'a', factory, panel_plan=plan)
            self.assertEqual(len(result['groups']), 1)
            self.assertEqual(result['groups'][0]['errors'], 1)
            self.assertEqual(result['groups'][0]['no_ai_answers'], 1)
            self.assertEqual(result['groups'][0]['successful_tests'], 1)
            self.assertEqual(result['groups'][0]['score'], 0)
            changed = deepcopy(plan)
            changed['queries'][1]['prompt'] += ' Include setup friction.'
            revised = answer_panel(root, {'id': 'C-fixture', 'market': 'en-US'}, root / 'b', factory, panel_plan=changed)
            self.assertNotEqual(result['panel_fingerprint'], revised['panel_fingerprint'])
            self.assertNotEqual(result['panel_plan_sha256'], revised['panel_plan_sha256'])
            both = answer_panel(root, {'id': 'C-fixture', 'market': 'both'}, root / 'both', factory, panel_plan=plan)
            self.assertNotEqual(result['panel_fingerprint'], both['panel_fingerprint'])

    def test_invalid_core_configuration_fails_before_sampling_or_html_fetch(self):
        invalid = []
        for field, value in [('model', 'a-different-model'), ('version', True), ('surface', 'consumer')]:
            plan = self.core_plan()
            plan[field] = value
            invalid.append(plan)
        plan = self.core_plan()
        plan['queries'][1]['id'] = plan['queries'][0]['id']
        invalid.append(plan)
        plan = self.core_plan()
        plan['queries'][1]['product_line'] = 'mouse'
        invalid.append(plan)
        plan = self.core_plan()
        plan['queries'][0]['id'] = '../../escaped'
        invalid.append(plan)
        plan = self.core_plan()
        plan['queries'][0]['prompt'] = 'Would Angry Miao be a good choice?'
        invalid.append(plan)
        for plan in invalid:
            with self.subTest(plan=plan), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                def factory(cwd):
                    self.fail('Invalid plan must not create a sampler')
                with self.assertRaises(ValueError):
                    answer_panel(root, {'id': 'C-invalid', 'market': 'both'}, root / 'results', factory, panel_plan=plan)
                self.assertFalse((root / 'results').exists())
                (root / 'config').mkdir()
                (root / 'config/answer-panel.json').write_text(json.dumps(plan))
                with patch('am_seo.measurement.technical_panel', side_effect=AssertionError('No fetch before plan validation')):
                    with self.assertRaises(ValueError):
                        measure(root, {'id': 'C-invalid', 'market': 'both'})

    def test_evaluate_uses_configured_core_panel_and_pinned_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'config').mkdir()
            (root / 'config/answer-panel.json').write_text(json.dumps(self.core_plan()))
            models = []
            def make_runner(cwd, model=None):
                models.append(model)
                self.assertNotEqual(cwd, root)
                return lambda *args, **kwargs: {'result': {'status': 'completed', 'answer_text': 'Neutral fixture.', 'citations': []},
                                              'trace': {'cli_version': 'fixture-cli', 'web_search_events': [{'query': 'fixture query'}]}}
            with patch('am_seo.measurement.technical_panel', return_value={'score': None, 'status': 'error'}), patch('am_seo.workflow.CodexRunner', side_effect=make_runner):
                result = measure(root, {'id': 'C-core', 'market': 'both', 'tasks': []})
            self.assertEqual(models, ['gpt-6.1-sol'] * 4)
            self.assertEqual(result['geo']['panel_version'], 'core-discovery-answer-v1')
            self.assertEqual(result['geo']['observation_count'], 4)
            self.assertIsNone(result['geo']['score'])
            self.assertEqual(result['production_writes'], 0)

    def test_svg_accessibility_titles_do_not_become_the_document_title(self):
        html = '<head><title>Actual page</title></head><body><svg><title>Visa</title></svg><svg><title>PayPal</title></svg></body>'
        self.assertEqual(diagnose_html(html)['title'], 'Actual page')
        result = diagnose_html('<svg><title>Visa</title></svg>')
        self.assertFalse(next(c['passed'] for c in result['checks'] if c['id'] == 'title'))

    def test_html_diagnostic_is_explicit_and_noindex_is_not_search_visibility(self):
        html = '<html lang="en"><title>Title</title><meta name="description" content="Description"><link rel="canonical" href="https://example.com/"><h1>Heading</h1></html>'
        result = diagnose_html(html)
        self.assertEqual(len(result['checks']), 6)
        self.assertTrue(all(c['passed'] for c in result['checks']))
        self.assertFalse(diagnose_html(html, headers={'X-Robots-Tag': 'noindex'})['checks'][-1]['passed'])
        self.assertFalse(any(c['passed'] for c in diagnose_html(html, http_status=404)['checks']))
        self.assertIn('不代表', result['note'])

    def test_technical_fetch_errors_do_not_create_a_zero_score(self):
        with tempfile.TemporaryDirectory() as temporary:
            def fail(url):
                raise OSError('fixture network failure')
            result = technical_panel(Path(temporary), fetcher=fail)
            self.assertIsNone(result['score'])
            self.assertEqual(result['errors'], 3)
            self.assertEqual(result['checks_total'], 0)

    def test_no_ai_answers_count_zero_errors_are_separate_and_locales_never_merge(self):
        result = summarize_answers([
            {'locale': 'zh-CN', 'status': 'completed', 'brand_mentioned': True},
            {'locale': 'zh-CN', 'status': 'no_ai_answer'},
            {'locale': 'zh-CN', 'status': 'error'},
            {'locale': 'en-US', 'status': 'error'},
        ])
        self.assertIsNone(result['score'])
        groups = {g['locale']: g for g in result['groups']}
        self.assertEqual(groups['zh-CN']['score'], 50)
        self.assertEqual(groups['zh-CN']['successful_tests'], 2)
        self.assertEqual(groups['zh-CN']['errors'], 1)
        self.assertEqual(groups['zh-CN']['no_ai_answers'], 1)
        self.assertIsNone(groups['en-US']['score'])

    def test_answer_panel_is_neutral_and_requires_actual_search_trace(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'outputs/agent-kit/query-seeds.json'
            source.parent.mkdir(parents=True)
            source.write_text(json.dumps({'queries': [
                {'id': 'EN-M-02', 'language': 'en-US', 'prompt': 'Which mice have replaceable batteries?'},
                {'id': 'ZH-M-02', 'language': 'zh-CN', 'prompt': '哪些鼠标可以更换电池？'},
            ]}))
            calls = []
            def factory(cwd):
                self.assertNotEqual(cwd, root)
                self.assertFalse((cwd / 'AGENTS.md').exists())
                def run(prompt, schema, directory, search=True):
                    self.assertNotIn('Angry Miao', prompt)
                    self.assertNotIn('怒喵', prompt)
                    self.assertTrue(search)
                    calls.append(prompt)
                    return {'result': {'status': 'completed', 'answer_text': 'Angry Miao has a replaceable-battery option.', 'citations': ['https://store.angrymiao.com/products/example']},
                            'trace': {'web_search_events': [{'query': 'fixture query'}]}}
                return run
            result = answer_panel(root, {'id': 'C-fixture', 'market': 'both'}, root / 'observations', factory)
            self.assertEqual(len(calls), 2)
            self.assertEqual({g['score'] for g in result['groups']}, {100})
            self.assertTrue(result['panel_fingerprint'])
            self.assertTrue((root / 'observations/observations.jsonl').is_file())
            def no_search(cwd):
                return lambda *a, **k: {'result': {'status': 'completed', 'answer_text': 'unsupported result', 'citations': []}, 'trace': {}}
            failed = answer_panel(root, {'id': 'C-no-search', 'market': 'en-US'}, root / 'no-search', no_search)
            self.assertEqual(failed['groups'][0]['errors'], 1)
            self.assertIsNone(failed['groups'][0]['score'])


if __name__ == '__main__':
    unittest.main()
