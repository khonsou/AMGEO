"""Brand inputs are immutable planning provenance, never live measurement evidence."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from am_seo.brand_context import load_brand_context
from am_seo.workflow import WorkflowEngine
from test_workflow import FixtureRunner


class BrandContextTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='amseo-brand-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.write('config/project.json', {'name': 'AM SEO', 'brand': {'name': 'Angry Miao', 'product_categories': ['键盘', '鼠标']}})
        self.write('config/upstreams.lock.json', {'upstreams': []})
        self.write('outputs/agent-kit/product-facts.json', {'facts': []})
        self.write('outputs/agent-kit/capabilities.json', {})
        self.write('outputs/agent-kit/geo-run-plan.json', {'panel': 'fixed neutral measurement'})
        self.runner = FixtureRunner()
        self.engine = WorkflowEngine(self.root, runner=self.runner)

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return path

    def brand(self, version=1):
        files = []
        commit = 'a' * 40
        for name in ['brand.md', 'audience.md', 'methodology.md', 'product.md', 'visual.md']:
            path = self.root / 'outputs/brand-context/sources' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Temporary reference fixture ' + name, encoding='utf-8')
            files.append({'path': f'am-marketing-planner/references/{name}', 'local_path': str(path.relative_to(self.root)),
                          'source_url': f'https://github.com/example/brand/blob/{commit}/am-marketing-planner/references/{name}',
                          'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size})
        self.write('outputs/brand-context/source-manifest.json', {'repository': 'https://github.com/example/brand', 'commit': commit, 'files': files})
        return self.write('config/brand-context.json', {'version': version, 'status': 'adopted_planning_context',
                  'source_manifest': 'outputs/brand-context/source-manifest.json',
                  'positioning': {'core': f'Future Art v{version}'},
                  'personas': [{'id': 'A', 'name': 'Engineering creator', 'priority': 'core', 'needs': ['Flow'], 'discovery': {'en-US': ['reviews']}, 'content_angles': ['design and experience']}],
                  'markets': {}, 'methodology': [], 'rules': ['No unsupported claims'], 'quarantined_claims': []})

    def wait(self):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = self.engine.state()
            if not state['active']:
                return state
            time.sleep(.01)
        self.fail('fixture agent did not finish')

    def analyze(self):
        result = self.engine.start('analyze')
        return next(c for c in self.wait()['cycles'] if c['id'] == result['cycle']['id'])

    def imported(self, previous=None):
        payload = {'executor': 'current_chat_agent', 'result': copy.deepcopy(self.runner.plan),
                   'research': {'summary': 'Read source references in the authorized chat.',
                                'source_urls': ['https://github.com/example/brand'], 'observed_at': '2026-11-01T10:30:00+00:00'}}
        return self.engine.start('import-analysis', cycle_id=previous, payload=payload)['cycle']

    def test_sources_require_all_five_files_and_exact_content_commit(self):
        self.brand()
        context = load_brand_context(self.root)
        self.assertTrue(context['integrity']['verified'])
        self.assertEqual(context['integrity']['files_verified'], 5)
        (self.root / 'outputs/brand-context/sources/audience.md').write_text('changed')
        context = load_brand_context(self.root)
        self.assertFalse(context['integrity']['verified'])
        with self.assertRaisesRegex(ValueError, '完整性'):
            self.engine.start('analyze')
        self.assertEqual(self.engine.state()['cycles'], [])
        self.assertEqual(self.runner.calls, [])

    def test_changed_context_is_stale_without_rewriting_cycle_or_phase_inputs(self):
        self.brand()
        cycle = self.analyze()
        original = copy.deepcopy(cycle['brand_context_snapshot'])
        project_original = copy.deepcopy(cycle['project_snapshot'])
        self.brand(2)
        self.write('config/project.json', {'brand': {'name': 'Changed brand'}})
        current = self.engine.state()['cycles'][0]
        self.assertEqual(current['brand_context_status'], 'stale')
        self.assertEqual(current['brand_context_snapshot'], original)
        self.assertEqual(self.engine._context(current)['project'], project_original)
        self.assertEqual(self.engine._context(current)['brand_context']['context']['positioning']['core'], 'Future Art v1')
        next_cycle = self.imported(current['id'])
        self.assertEqual(next_cycle['brand_context_snapshot']['version'], 2)
        self.assertEqual(self.engine.state()['cycles'][-1]['brand_context_status'], 'current')

    def test_legacy_cycle_is_not_retroactively_attributed_to_brand_sources(self):
        cycle = self.analyze()
        saved = self.engine.data['cycles'][0]
        saved.pop('brand_context_snapshot')
        saved.pop('project_snapshot')
        self.brand()
        state = self.engine.state()['cycles'][0]
        self.assertEqual(state['brand_context_status'], 'legacy_unversioned')
        data = self.engine._context(state)
        self.assertEqual(data['brand_context']['status'], 'legacy_unversioned')
        self.assertNotIn('Future Art', json.dumps(data['brand_context']))
        self.assertIn('unavailable', data['project']['historical_snapshot_status'])

    def test_manifest_only_commit_change_is_stale_but_retrieval_time_is_not(self):
        self.brand()
        cycle = self.analyze()
        first_sha = cycle['brand_context_snapshot']['sha256']
        path = self.root / 'outputs/brand-context/source-manifest.json'
        manifest = json.loads(path.read_text())
        manifest['retrieved_at'] = '2026-11-02T00:00:00Z'
        self.write(str(path.relative_to(self.root)), manifest)
        self.assertEqual(load_brand_context(self.root)['sha256'], first_sha)
        old = manifest['commit']
        manifest['commit'] = 'b' * 40
        for entry in manifest['files']:
            entry['source_url'] = entry['source_url'].replace(old, manifest['commit'])
        self.write(str(path.relative_to(self.root)), manifest)
        current = load_brand_context(self.root)
        self.assertTrue(current['integrity']['verified'])
        self.assertNotEqual(current['sha256'], first_sha)
        self.assertEqual(self.engine.state()['cycles'][0]['brand_context_status'], 'stale')

    def test_execution_verification_and_improvement_share_frozen_brand_inputs(self):
        self.brand()
        cycle = self.analyze()
        self.brand(2)
        for action in ['execute', 'verify']:
            self.engine.start(action, cycle_id=cycle['id'], task_id=cycle['tasks'][0]['id'])
            self.wait()
        saved = self.engine.data['cycles'][0]
        saved['metrics'] = {'seo': {'score': None}, 'geo': {'score': None}, 'execution': {}}
        self.engine.start('improve', cycle_id=cycle['id'])
        self.wait()
        for call in self.runner.calls:
            data = json.loads(call['prompt'].split('Project input JSON:\n', 1)[1])
            self.assertEqual(data['brand_context']['version'], 1)
            self.assertEqual(data['brand_context']['context']['positioning']['core'], 'Future Art v1')
        self.assertIn('brand_context', json.loads(self.runner.calls[-1]['prompt'].split('Project input JSON:\n', 1)[1]))

    def test_local_review_supersedes_only_category_bound_legacy_direction(self):
        self.brand()
        cycle = self.imported()
        change = '下一轮按目标补充键盘的公开评测、社区和产品事实；本轮鼠标结果不外推为整个品牌的结论。'
        unrelated = '保留键盘使用问题的来源和日期。'
        old = {'version': 2, 'status': 'candidate_for_next_cycle',
               'priorities': [change, unrelated, '证据与型号准确性'],
               'lessons': [{'finding': '旧品类覆盖不足', 'change': change,
                            'evidence': cycle['id'] + '.tasks; config.project.brand.product_categories',
                            'scope': 'process', 'status': 'adopted_process_candidate'},
                           {'finding': '保留产品来源', 'change': unrelated, 'evidence': 'metrics.execution',
                            'scope': 'process', 'status': 'adopted_process_candidate'}]}
        self.engine.data['strategy'] = copy.deepcopy(old)
        archive = self.write('outputs/runtime/console/workflow/strategies/v2.json', old)
        archived_bytes = archive.read_bytes()
        path = self.brand(2)
        updated = json.loads(path.read_text())
        lines = ['电竞鼠标 / AM Infinity Mouse', 'AI device / 例如 CYBERBOARD R6']
        updated['user_direction'] = {'adopted_product_lines': lines, 'recorded_date': '2026-11-01'}
        self.write(str(path.relative_to(self.root)), updated)
        self.write('config/project.json', {'brand': {'name': 'Angry Miao', 'product_categories': lines}})
        self.engine.start('local-review', cycle_id=cycle['id'])
        strategy = self.engine.state()['strategy']
        self.assertEqual(strategy['version'], 3)
        self.assertNotIn(change, strategy['priorities'])
        self.assertIn(unrelated, strategy['priorities'])
        retired = next(lesson for lesson in strategy['lessons'] if lesson['change'] == change)
        self.assertEqual(retired['status'], 'superseded_brand_direction')
        self.assertEqual(strategy['lessons'][1]['status'], 'adopted_process_candidate')
        self.assertEqual(strategy['brand_context_sha256'], load_brand_context(self.root)['sha256'])
        self.assertEqual(strategy['adopted_product_lines'], lines)
        self.assertTrue(any('user_direction.adopted_product_lines' in lesson['change'] for lesson in strategy['lessons']))
        self.assertEqual(archive.read_bytes(), archived_bytes)
        self.assertEqual(old['lessons'][0]['status'], 'adopted_process_candidate')
        self.engine.start('local-review', cycle_id=cycle['id'])
        self.assertEqual(self.engine.state()['strategy']['version'], 3)
        self.assertEqual(self.runner.calls, [])

    def test_import_is_actual_attributed_analysis_without_provider_or_measurement(self):
        self.brand()
        panel = (self.root / 'outputs/agent-kit/geo-run-plan.json').read_bytes()
        first = self.imported()
        second = self.imported(first['id'])
        self.assertEqual(self.runner.calls, [])
        self.assertEqual(second['previous_cycle_id'], first['id'])
        self.assertEqual(second['analysis_scope'], 'current_chat_agent_analysis_imported')
        self.assertEqual(second['external_analysis']['backend_model_calls'], 0)
        self.assertFalse(second['external_analysis']['independently_verified'])
        self.assertNotIn('traces', second)
        self.assertIsNone(second['metrics'])
        self.assertEqual(second['tasks'][0]['status'], 'ready')
        self.assertEqual(second['findings'][0]['evidence_status'], 'agent_reported_pending_verification')
        self.assertEqual((self.root / 'outputs/agent-kit/geo-run-plan.json').read_bytes(), panel)
        restored = WorkflowEngine(self.root, runner=self.runner)
        self.assertEqual(restored.state()['cycles'][-1]['brand_context_snapshot'], second['brand_context_snapshot'])

    def test_import_rejects_ambiguous_authority_bad_sources_and_bad_task_ownership(self):
        self.brand()
        base = {'executor': 'current_chat_agent', 'result': copy.deepcopy(self.runner.plan),
                'research': {'summary': 'Read references.', 'source_urls': ['https://github.com/example/brand'], 'observed_at': '2026-11-01T10:30:00Z'}}
        payloads = []
        wrong = copy.deepcopy(base); wrong['executor'] = 'new_agent_admin'; payloads.append(wrong)
        wrong = copy.deepcopy(base); wrong['research']['source_urls'] = ['http://127.0.0.1/secret']; payloads.append(wrong)
        wrong = copy.deepcopy(base); wrong['research']['observed_at'] = '2026-11-01T10:30:00'; payloads.append(wrong)
        wrong = copy.deepcopy(base); wrong['result']['tasks'][0]['owner'] = 'human'; payloads.append(wrong)
        for payload in payloads:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.engine.start('import-analysis', payload=payload)
            self.assertEqual(self.engine.state()['cycles'], [])
        self.assertEqual(self.runner.calls, [])


if __name__ == '__main__':
    unittest.main()
