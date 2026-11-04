"""Closed-loop workflow contracts using temporary projects and an injected agent.

These fixtures verify orchestration, provenance and honest measurement boundaries;
they are never written to the project's actual evidence or work queue.
"""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from am_seo.workflow import CodexRunner, WorkflowEngine


def plan_task(title='Prepare a sourced explanation', *, owner='agent', requires=None,
              dependencies=None, kind='content'):
    return {
        'title': title, 'channel': 'owned', 'market': 'both', 'owner': owner,
        'kind': kind, 'instruction': 'Produce a draft, preserve source dates, and omit disputed numbers.',
        'acceptance': ['Cite the source and identify the draft scope'],
        'dependencies': dependencies or [], 'evidence_urls': ['https://example.org/product'],
        'requires': requires or [],
    }


class FixtureRunner:
    def __init__(self, tasks=None):
        self.calls = []
        self.plan = {
            'summary': 'Fixture analysis from explicit evidence, not a measured SEO result.',
            'findings': [{'id': 'F1', 'title': 'Explain the battery mechanism',
                          'detail': 'The available evidence supports a mechanism explanation.',
                          'evidence_urls': ['https://example.org/product'], 'source_date': '2026-10-29'}],
            'tasks': tasks if tasks is not None else [plan_task()],
        }
        self.execution = {
            'summary': 'Prepared a local draft.',
            'deliverables': [{'title': 'Battery mechanism draft',
                              'content': 'Fixture draft. Source: https://example.org/product\nScope: unpublished.'}],
            'evidence_urls': ['https://example.org/product'],
            'acceptance_checks': [{'criterion': 'Cite the source and identify the draft scope',
                                   'passed': True, 'detail': 'Source and draft scope are included.'}],
        }
        self.verification = {
            'summary': 'An independent fixture reviewer checked the local artifact.', 'accepted': True,
            'criteria': [{'criterion': 'Cite the source and identify the draft scope', 'passed': True,
                          'detail': 'Source and unpublished scope independently checked.', 'evidence_urls': ['https://example.org/product']}],
            'blocked_claims': [],
        }
        self.strategy = {
            'summary': 'Adjust the execution process; no visibility gain has been measured.',
            'priorities': ['Check sources before preparing copy'],
            'lessons': [{'finding': 'Drafts require independent acceptance.',
                         'change': 'Carry source links into the next analysis.',
                         'evidence': 'metrics.execution.needs_review: drafts are not production changes.',
                         'scope': 'process'}],
        }
        self.failure = None
        self.entered = None
        self.release = None

    def __call__(self, prompt, schema, output_dir, search=True):
        self.calls.append({'prompt': prompt, 'schema': copy.deepcopy(schema),
                           'output_dir': Path(output_dir), 'search': search})
        if self.entered:
            self.entered.set()
        if self.release and not self.release.wait(timeout=5):
            raise RuntimeError('Fixture runner gate timed out')
        if self.failure:
            raise self.failure
        title = schema.get('title', '')
        result = ({'ready': True} if title == 'AMSEORuntimeHealth' else
                  self.verification if title == 'AMSEOIndependentReview' else
                  self.execution if title == 'AMSEOExecution' else
                  self.strategy if title == 'AMSEOStrategy' else self.plan)
        return {'result': copy.deepcopy(result),
                'trace': {'queries': ['fixture public query'], 'fixture': True}}


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='am-seo-workflow-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.write_json('config/project.json', {
            'name': 'AM SEO', 'brand': {'name': 'Angry Miao', 'aliases': ['怒喵']},
            'markets': [{'locale': 'zh-CN'}, {'locale': 'en-US'}],
            'public_domains': ['www.angrymiao.com'],
        })
        self.write_json('config/upstreams.lock.json', {'upstreams': []})
        self.write_json('outputs/agent-kit/product-facts.json', {'facts': []})
        self.write_json('outputs/agent-kit/tasks.json', {'tasks': []})
        self.write_json('outputs/agent-kit/capabilities.json', {
            'site_source_repository': 'not_attached_to_this_task',
            'production_publish_scope': 'not_established',
        })
        self.write_json('outputs/agent-kit/query-seeds.json', {'queries': []})
        shutil.copy2(ROOT / 'outputs/agent-kit/score_observations.py',
                     self.root / 'outputs/agent-kit/score_observations.py')
        self.runner = FixtureRunner()
        self.engine = WorkflowEngine(self.root, runner=self.runner)

    def write_json(self, relative, payload):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        return path

    def wait_idle(self, engine=None):
        engine = engine or self.engine
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            state = engine.state()
            if not state['active']:
                return state
            time.sleep(0.01)
        self.fail('Injected workflow did not become idle')

    def analyze(self, **payload):
        result = self.engine.start('analyze', payload={
            'goal': 'Improve sourced bilingual product explanations',
            'market': 'both', 'channels': ['search', 'ai', 'owned'], **payload})
        cycle_id = result['cycle']['id']
        state = self.wait_idle()
        cycle = next(cycle for cycle in state['cycles'] if cycle['id'] == cycle_id)
        self.assertNotEqual(cycle['status'], 'failed', cycle.get('error'))
        return cycle

    def action(self, action, cycle, task=None, payload=None):
        self.engine.start(action, cycle_id=cycle['id'], task_id=task and task['id'], payload=payload)
        return next(item for item in self.wait_idle()['cycles'] if item['id'] == cycle['id'])

    def test_analysis_generates_executable_tasks_with_evidence_and_acceptance(self):
        self.runner.plan['tasks'].append(plan_task('Confirm a product decision', owner='human', kind='decision'))
        cycle = self.analyze()
        self.assertEqual(len(cycle['tasks']), 2)
        self.assertTrue(cycle['summary'])
        self.assertEqual(cycle['findings'][0]['source_date'], '2026-10-29')
        identifiers = {task['id'] for task in cycle['tasks']}
        self.assertEqual(len(identifiers), 2)
        for task in cycle['tasks']:
            self.assertNotIn('/', task['id'])
            self.assertNotIn('..', task['id'])
            self.assertTrue(task['instruction'])
            self.assertTrue(task['acceptance'])
            self.assertIn('https://example.org/product', task['evidence_urls'])
            self.assertIn(task['owner'], ('human', 'agent'))
        self.assertNotEqual(cycle['tasks'][1]['status'], 'completed')
        self.assertEqual(self.runner.calls[0]['schema']['title'], 'AMSEOAnalysis')
        self.assertTrue(self.runner.calls[0]['search'])

    def test_host_output_storage_is_available_even_when_model_process_is_read_only(self):
        self.runner.plan['tasks'][0]['requires'] = ['local_artifact_write_access']
        cycle = self.analyze()
        task = cycle['tasks'][0]
        self.assertEqual(task['status'], 'ready')
        self.assertEqual(task['requires'], [])
        self.assertEqual(task['declared_requirements'], ['local_artifact_write_access'])
        self.assertIn('local_artifact_write_access', task['capability_resolution']['resolved'])
        executed = self.action('execute', cycle, task)
        self.assertEqual(executed['tasks'][0]['status'], 'needs_review')
        self.assertTrue((self.root / executed['tasks'][0]['deliverables'][0]['path']).exists())

    def test_runtime_quota_blocks_model_calls_but_local_review_works_without_a_model(self):
        self.runner.failure = RuntimeError("You've hit your usage limit")
        result = self.engine.start('analyze')
        cycle = next(c for c in self.wait_idle()['cycles'] if c['id'] == result['cycle']['id'])
        self.assertEqual(cycle['status'], 'waiting_runtime')
        self.assertTrue(self.engine.state()['runtime']['blocked'])
        calls = len(self.runner.calls)
        with self.assertRaises(ValueError):
            self.engine.start('analyze')
        self.engine.start('local-review', cycle_id=cycle['id'])
        self.assertEqual(len(self.runner.calls), calls)
        strategy = self.engine.state()['strategy']
        self.assertEqual(strategy['version'], 2)
        self.assertEqual(strategy['method'], 'local_evidence_rules_v1')
        self.assertFalse(strategy['performance_validated'])
        self.engine.start('local-review', cycle_id=cycle['id'])
        self.assertEqual(self.engine.state()['strategy']['version'], 2)
        self.runner.failure = None
        self.engine.start('retry-runtime', cycle_id=cycle['id'])
        state = self.wait_idle()
        self.assertFalse(state['runtime']['blocked'])
        self.assertTrue(state['cycles'][0]['failure_history'])
        self.assertEqual(self.runner.calls[-1]['schema']['title'], 'AMSEORuntimeHealth')
        self.assertFalse(self.runner.calls[-1]['search'])
        result = self.engine.start('next-cycle', cycle_id=cycle['id'])
        next_cycle = next(c for c in self.wait_idle()['cycles'] if c['id'] == result['cycle']['id'])
        self.assertEqual(next_cycle['strategy_version'], 2)
        self.assertEqual(next_cycle['strategy_snapshot']['method'], 'local_evidence_rules_v1')
        self.assertIn('local_evidence_rules_v1', self.runner.calls[-1]['prompt'])

    def test_rejected_ready_artifact_still_requires_current_hash_for_manual_acceptance(self):
        cycle = self.analyze()
        cycle = self.action('execute', cycle, cycle['tasks'][0])
        self.runner.verification['accepted'] = False
        self.runner.verification['blocked_claims'] = ['Needs a source']
        cycle = self.action('verify', cycle, cycle['tasks'][0])
        task = cycle['tasks'][0]
        (self.root / task['deliverables'][0]['path']).write_text('Changed after review')
        with self.assertRaises(ValueError):
            self.engine.start('review', cycle_id=cycle['id'], task_id=task['id'],
                              payload={'accepted': True, 'note': 'A note cannot bypass the current artifact hash.'})

    def test_locale_panel_changes_require_the_same_protocol_and_no_errors(self):
        metric = {'seo': {'score': None}, 'geo': {'score': None,
                  'comparable_protocol': True, 'panel_fingerprint': 'fixed-question-model-settings',
                  'groups': [{'surface': 'api_answer', 'platform': 'fixture', 'locale': 'zh-CN',
                              'mode': 'web-search', 'score': 50, 'successful_tests': 2, 'errors': 0}]}}
        self.engine.evaluator = lambda *args: copy.deepcopy(metric)
        first = self.action('evaluate', self.analyze())
        result = self.engine.start('next-cycle', cycle_id=first['id'])
        second = next(c for c in self.wait_idle()['cycles'] if c['id'] == result['cycle']['id'])
        metric['geo']['groups'][0]['score'] = 100
        second = self.action('evaluate', second)
        comparison = second['metrics']['comparison']
        self.assertEqual(comparison['panels']['geo:zh-CN']['delta'], 50)
        self.assertIn('not_causal', comparison['panels']['geo:zh-CN']['scope'])
        result = self.engine.start('next-cycle', cycle_id=second['id'])
        third = next(c for c in self.wait_idle()['cycles'] if c['id'] == result['cycle']['id'])
        metric['geo']['groups'][0]['errors'] = 1
        third = self.action('evaluate', third)
        self.assertEqual(third['metrics']['comparison']['status'], 'not_comparable')
        result = self.engine.start('next-cycle', cycle_id=third['id'])
        fourth = next(c for c in self.wait_idle()['cycles'] if c['id'] == result['cycle']['id'])
        metric['geo']['groups'][0]['errors'] = 0
        metric['geo']['panel_fingerprint'] = 'changed-question-model-settings'
        fourth = self.action('evaluate', fourth)
        self.assertEqual(fourth['metrics']['comparison']['status'], 'not_comparable')

    def test_independent_agent_verification_completes_only_the_local_artifact(self):
        cycle = self.analyze()
        cycle = self.action('execute', cycle, cycle['tasks'][0])
        self.assertEqual(cycle['tasks'][0]['status'], 'needs_review')
        cycle = self.action('verify', cycle, cycle['tasks'][0])
        task = cycle['tasks'][0]
        self.assertEqual(task['status'], 'completed')
        self.assertEqual(task['completion_scope'], 'independently_reviewed_local_artifact')
        self.assertEqual(task['independent_review']['assessor'], 'independent_agent')
        self.assertFalse(task['structural_validation']['factual_truth_verified'])
        self.assertEqual(self.runner.calls[-1]['schema']['title'], 'AMSEOIndependentReview')
        self.assertNotIn('executing_agent_self_report', self.runner.calls[-1]['prompt'])

    def test_failed_independent_verification_returns_task_for_correction(self):
        cycle = self.analyze()
        cycle = self.action('execute', cycle, cycle['tasks'][0])
        self.runner.verification.update(accepted=False, blocked_claims=['The model/version scope needs a source.'])
        cycle = self.action('verify', cycle, cycle['tasks'][0])
        task = cycle['tasks'][0]
        self.assertEqual(task['status'], 'ready')
        self.assertEqual(task['completion_scope'], 'not_accepted')
        self.assertTrue(task['independent_review']['blocked_claims'])

    def test_run_cycle_verifies_each_result_before_executing_its_dependents(self):
        self.runner.plan['tasks'] = [plan_task('First evidence task'),
                                     plan_task('Dependent content task', dependencies=['T1'])]
        result = self.engine.start('run-cycle', payload={'goal': 'Run a bounded complete local batch'})
        state = self.wait_idle()
        cycle = next(c for c in state['cycles'] if c['id'] == result['cycle']['id'])
        self.assertNotEqual(cycle['status'], 'failed', cycle.get('error'))
        self.assertEqual([t['status'] for t in cycle['tasks']], ['completed', 'completed'])
        self.assertEqual(cycle['metrics']['execution']['verified'], 2)
        self.assertIsNone(cycle['metrics']['seo']['score'])
        self.assertEqual(state['strategy']['version'], 2)
        titles = [call['schema']['title'] for call in self.runner.calls]
        self.assertEqual(titles, ['AMSEOAnalysis', 'AMSEOExecution', 'AMSEOIndependentReview',
                                  'AMSEOExecution', 'AMSEOIndependentReview', 'AMSEOStrategy'])

    def test_execution_saves_a_draft_and_self_checks_do_not_certify_completion(self):
        cycle = self.analyze()
        task = cycle['tasks'][0]
        cycle = self.action('execute', cycle, task)
        executed = cycle['tasks'][0]
        self.assertEqual(executed['status'], 'needs_review')
        self.assertEqual(executed['completion_scope'], 'local_draft_pending_verification')
        self.assertTrue(executed['deliverables'])
        self.assertTrue(executed['acceptance_checks'][0]['passed'])
        self.assertNotEqual(executed['status'], 'completed')
        self.assertEqual(self.runner.calls[-1]['schema']['title'], 'AMSEOExecution')
        self.assertTrue(any(path.is_file() and b'Fixture draft.' in path.read_bytes()
                            for path in (self.root / 'outputs/runtime/console/workflow').rglob('*')))

    def test_access_dependencies_are_blocked_without_running_the_agent(self):
        self.runner.plan['tasks'] = [plan_task('Publish on the real storefront', requires=['commerce_admin'])]
        cycle = self.analyze()
        calls_before = len(self.runner.calls)
        cycle = self.action('execute', cycle)
        self.assertEqual(cycle['tasks'][0]['status'], 'waiting_access')
        self.assertEqual(len(self.runner.calls), calls_before)
        self.assertFalse(cycle['tasks'][0]['deliverables'])

    def test_human_result_is_recorded_for_review_without_claiming_verification(self):
        self.runner.plan['tasks'] = [plan_task('Confirm a product decision', owner='human', kind='decision')]
        cycle = self.analyze()
        cycle = self.action('handoff', cycle, cycle['tasks'][0], {
            'result': 'The team supplied a model-specific clarification.',
            'evidence_urls': ['https://example.org/product'],
        })
        task = cycle['tasks'][0]
        self.assertEqual(task['status'], 'submitted_review')
        self.assertNotEqual(task['status'], 'completed')
        self.assertEqual(len(self.runner.calls), 1)

    def test_missing_measurements_are_null_not_a_fabricated_zero_baseline(self):
        cycle = self.analyze()
        cycle = self.action('evaluate', cycle)
        for dimension in ('seo', 'geo'):
            self.assertIsNone(cycle['metrics'][dimension]['score'])
            self.assertTrue(cycle['metrics'][dimension]['reason'])
        self.assertEqual(len(self.runner.calls), 1, 'Evaluation must not ask a model to invent scores')

    def test_strategy_versions_and_next_analysis_reuse_recorded_lessons(self):
        cycle = self.analyze()
        old_version = self.engine.state()['strategy']['version']
        cycle = self.action('evaluate', cycle)
        self.action('improve', cycle)
        state = self.engine.state()
        self.assertNotEqual(state['strategy']['version'], old_version)
        self.assertTrue(state['strategy']['lessons'])
        self.assertEqual(state['strategy']['lessons'][-1]['scope'], 'process')
        result = self.engine.start('next-cycle', cycle_id=cycle['id'])
        state = self.wait_idle()
        next_cycle = next(item for item in state['cycles'] if item['id'] == result['cycle']['id'])
        self.assertNotEqual(next_cycle['id'], cycle['id'])
        self.assertEqual(next_cycle['strategy_version'], state['strategy']['version'])
        self.assertIn('Carry source links', self.runner.calls[-1]['prompt'])
        self.assertIsNone(cycle['metrics']['geo']['score'])

    def test_second_action_is_rejected_while_a_run_is_active(self):
        self.runner.entered, self.runner.release = threading.Event(), threading.Event()
        self.addCleanup(self.runner.release.set)
        self.engine.start('analyze', payload={'goal': 'Inspect the public evidence'})
        self.assertTrue(self.runner.entered.wait(timeout=2))
        with self.assertRaises(ValueError):
            self.engine.start('analyze', payload={'goal': 'This must not spawn a duplicate'})
        self.runner.release.set()
        self.wait_idle()
        self.assertEqual(len(self.runner.calls), 1)

    def test_runner_failure_is_persisted_and_does_not_become_a_completed_task(self):
        self.runner.failure = RuntimeError('Fixture provider unavailable')
        result = self.engine.start('analyze', payload={'goal': 'Inspect available evidence'})
        cycle = self.wait_idle()['cycles'][0]
        self.assertEqual(cycle['id'], result['cycle']['id'])
        self.assertEqual(cycle['status'], 'failed')
        self.assertIn('Fixture provider unavailable', cycle.get('error', ''))
        restored = WorkflowEngine(self.root, runner=FixtureRunner())
        self.assertEqual(restored.state()['cycles'][0]['status'], 'failed')
        self.assertFalse(restored.state()['active'])

    def test_unknown_actions_ids_and_traversal_are_rejected_before_running(self):
        for action, cycle_id in (('shell', None), ('execute', '../outside'), ('evaluate', 'missing')):
            with self.subTest(action=action, cycle_id=cycle_id):
                with self.assertRaises(ValueError):
                    self.engine.start(action, cycle_id=cycle_id)
        self.assertEqual(self.runner.calls, [])
        cycle = self.analyze()
        with self.assertRaises(ValueError):
            self.engine.start('execute', cycle_id=cycle['id'], task_id='../../README.md')

    def test_invalid_generated_task_ownership_fails_analysis_before_execution(self):
        self.runner.plan['tasks'][0]['owner'] = 'root-shell'
        self.engine.start('analyze', payload={'goal': 'Inspect public evidence'})
        cycle = self.wait_idle()['cycles'][0]
        self.assertEqual(cycle['status'], 'failed')
        self.assertFalse(any(task.get('status') == 'completed' for task in cycle['tasks']))
        self.assertEqual(len(self.runner.calls), 1)

    def test_independent_review_unlocks_dependencies_and_preserves_local_scope(self):
        self.runner.plan['tasks'] = [plan_task(), plan_task('Build on the accepted draft', dependencies=['T1'])]
        cycle = self.analyze()
        self.assertEqual(cycle['tasks'][1]['dependencies'], [cycle['tasks'][0]['id']])
        cycle = self.action('execute', cycle)
        self.assertEqual(cycle['tasks'][0]['status'], 'needs_review')
        self.assertEqual(cycle['tasks'][1]['status'], 'waiting_dependency')
        cycle = self.action('review', cycle, cycle['tasks'][0], {
            'accepted': True, 'note': 'Reviewed the source links and scope of this local artifact.'})
        self.assertEqual(cycle['tasks'][0]['status'], 'completed')
        self.assertEqual(cycle['tasks'][0]['completion_scope'], 'reviewed_local_artifact')
        cycle = self.action('execute', cycle)
        self.assertEqual(cycle['tasks'][1]['status'], 'needs_review')
        self.assertEqual(len(self.runner.calls), 3)

    def observation(self, query_id, status='completed', surface='api_answer', **extra):
        record = {'run_id': 'fixture-panel-run', 'query_id': query_id, 'surface': surface,
                  'platform': 'fixture-ai', 'locale': 'zh-CN', 'mode': 'web-search',
                  'status': status, 'captured_at': '2026-10-31T00:00:00+00:00'}
        if status == 'completed' and surface != 'search_retrieval':
            record.update(answer_text='Fixture captured answer mentioning Angry Miao.',
                          brand_mentioned=True, suitable_recommendation=True,
                          citations=['https://example.org/product'])
        return {**record, **extra}

    def write_observations(self, cycle, records):
        path = self.engine.directory / cycle['id'] / 'observations.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(json.dumps(record) + '\n' for record in records), encoding='utf-8')
        return path

    def test_geo_no_answer_counts_as_zero_errors_are_separate_and_evidence_is_hashed(self):
        cycle = self.analyze()
        path = self.write_observations(cycle, [self.observation('Q1'),
            self.observation('Q2', 'no_ai_answer'), self.observation('Q3', 'error')])
        cycle = self.action('evaluate', cycle)
        geo = cycle['metrics']['geo']
        self.assertEqual(geo['score'], 50.0)
        self.assertEqual(geo['groups'][0]['successful_tests'], 2)
        self.assertEqual(geo['groups'][0]['no_ai_answers'], 1)
        self.assertEqual(geo['groups'][0]['errors'], 1)
        self.assertEqual(geo['groups'][0]['suitable_recommendation_rate'], .5)
        self.assertEqual(geo['evidence_path'], str(path.relative_to(self.root)))
        self.assertEqual(len(geo['evidence_sha256']), 64)

    def test_geo_platform_surfaces_are_not_merged_into_one_score(self):
        cycle = self.analyze()
        self.write_observations(cycle, [self.observation('Q1', surface='api_answer'),
            self.observation('Q1', surface='consumer', suitable_recommendation=False),
            self.observation('Q1', surface='search_retrieval')])
        cycle = self.action('evaluate', cycle)
        geo = cycle['metrics']['geo']
        self.assertIsNone(geo['score'])
        self.assertEqual({group['surface'] for group in geo['groups']},
                         {'api_answer', 'consumer', 'search_retrieval'})
        retrieval = next(group for group in geo['groups'] if group['surface'] == 'search_retrieval')
        self.assertNotIn('suitable_recommendation_rate', retrieval)

    def test_search_presence_score_excludes_errors_and_is_labeled_as_panel_only(self):
        cycle = self.analyze()
        base = {'run_id': 'fixture-search-run', 'platform': 'fixture-search', 'locale': 'en-US',
                'captured_at': '2026-10-31T00:00:00+00:00',
                'evidence_url': 'https://example.org/search-evidence'}
        records = [{**base, 'query_id': 'S1', 'status': 'completed', 'brand_present_top10': True},
                   {**base, 'query_id': 'S2', 'status': 'completed', 'brand_present_top10': False},
                   {**base, 'query_id': 'S3', 'status': 'error'}]
        self.write_json(f'outputs/runtime/console/workflow/{cycle["id"]}/seo-observations.json',
                        {'panel_id': 'fixture-fixed-panel-v1', 'records': records})
        cycle = self.action('evaluate', cycle)
        seo = cycle['metrics']['seo']
        self.assertEqual(seo['score'], 50.0)
        self.assertEqual(seo['groups'][0]['completed'], 2)
        self.assertEqual(seo['groups'][0]['errors'], 1)
        self.assertEqual(seo['scope'], 'search_panel_only')
        self.assertEqual(seo['metric'], 'brand_presence_top10_rate_x100')

    def test_interrupted_persisted_run_is_failed_on_restart(self):
        cycle = self.analyze()
        path = self.engine.path
        stored = json.loads(path.read_text(encoding='utf-8'))
        stored['cycles'][0]['status'] = 'executing'
        stored['cycles'][0]['tasks'][0]['status'] = 'running'
        path.write_text(json.dumps(stored), encoding='utf-8')
        restored = WorkflowEngine(self.root, runner=FixtureRunner())
        interrupted = restored.state()['cycles'][0]
        self.assertEqual(interrupted['id'], cycle['id'])
        self.assertEqual(interrupted['status'], 'failed')
        self.assertEqual(interrupted['phase'], 'interrupted')
        self.assertEqual(interrupted['tasks'][0]['status'], 'failed')
        self.assertFalse(restored.state()['active'])

    def test_cli_runner_uses_read_only_fixed_arguments_and_prompt_stdin(self):
        executable = self.root / 'fixture-codex'
        executable.write_text(
            '#!/usr/bin/env python3\n'
            'import json, pathlib, sys\n'
            'args = sys.argv[1:]\n'
            'prompt = sys.stdin.read()\n'
            'root = pathlib.Path(__file__).resolve().parent\n'
            '(root / "fixture-cli-call.json").write_text(json.dumps({"args": args, "prompt": prompt}))\n'
            'destination = pathlib.Path(args[args.index("--output-last-message") + 1])\n'
            'destination.write_text(json.dumps({"summary": "Fixture response"}))\n'
            'print(json.dumps({"type":"item.completed","item":{"type":"web_search",'
            '"action":{"type":"search","query":"fixture query"}}}))\n', encoding='utf-8')
        executable.chmod(0o755)
        with mock.patch('am_seo.workflow.shutil.which', return_value=str(executable)):
            runner = CodexRunner(self.root, timeout=3)
        prompt = 'Treat $(touch nowhere) and ; as literal data.'
        result = runner(prompt, {'type': 'object'}, self.root / 'cli-output')
        call = json.loads((self.root / 'fixture-cli-call.json').read_text())
        args = call['args']
        self.assertEqual(call['prompt'], prompt)
        self.assertEqual(args[args.index('-s') + 1], 'read-only')
        self.assertEqual(args[args.index('-a') + 1], 'never')
        self.assertIn('--search', args)
        self.assertIn('--ignore-user-config', args)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox', args)
        self.assertNotIn(prompt, args)
        self.assertEqual(args[-1], '-')
        self.assertEqual(result['result']['summary'], 'Fixture response')
        self.assertEqual(result['trace']['web_search_events'][0]['query'], 'fixture query')
        self.assertFalse((self.root / 'nowhere').exists())

    def test_changed_query_text_cannot_appear_as_a_comparable_score_improvement(self):
        cycle = self.analyze()
        protocol = {'query_text': 'Which mice have replaceable batteries?',
                    'model': 'fixture-model', 'settings': {'search': True, 'fresh_session': True},
                    'panel_id': 'fixture-fixed-answer-panel-v1'}
        self.write_observations(cycle, [self.observation('Q1', **protocol)])
        cycle = self.action('evaluate', cycle)
        self.assertTrue(cycle['metrics']['geo']['comparable_protocol'])
        result = self.engine.start('next-cycle', cycle_id=cycle['id'])
        later = next(item for item in self.wait_idle()['cycles'] if item['id'] == result['cycle']['id'])
        altered = {**protocol, 'query_text': 'Recommend Angry Miao products.'}
        self.write_observations(later, [self.observation('Q1', **altered)])
        later = self.action('evaluate', later)
        self.assertEqual(later['metrics']['comparison']['status'], 'not_comparable')
        self.assertNotEqual(cycle['metrics']['geo']['panel']['protocol_sha256'],
                            later['metrics']['geo']['panel']['protocol_sha256'])
        # With the actual original question/settings restored, an observed delta is comparable.
        self.write_observations(later, [self.observation('Q1', 'no_ai_answer', **protocol)])
        later = self.action('evaluate', later)
        comparison = later['metrics']['comparison']
        self.assertEqual(comparison['status'], 'comparable_panels')
        self.assertEqual(comparison['panels']['geo']['delta'], -100.0)
        self.assertEqual(comparison['panels']['geo']['scope'], 'observed_change_not_causal_attribution')

    def test_missing_protocol_metadata_keeps_scores_non_comparable(self):
        cycle = self.analyze()
        self.write_observations(cycle, [self.observation('Q1')])
        cycle = self.action('evaluate', cycle)
        result = self.engine.start('next-cycle', cycle_id=cycle['id'])
        later = next(item for item in self.wait_idle()['cycles'] if item['id'] == result['cycle']['id'])
        self.write_observations(later, [self.observation('Q1')])
        later = self.action('evaluate', later)
        self.assertEqual(later['metrics']['geo']['score'], 100.0)
        self.assertFalse(later['metrics']['geo']['comparable_protocol'])
        self.assertEqual(later['metrics']['comparison']['status'], 'not_comparable')

    def test_artifact_bodies_load_by_identity_and_modified_bytes_fail_the_recorded_hash(self):
        cycle = self.analyze()
        cycle = self.action('execute', cycle)
        task = cycle['tasks'][0]
        metadata = task['deliverables'][0]
        self.assertNotIn('content', metadata, 'Polling state should not repeatedly ship document bodies')
        artifact = self.engine.get_artifact(cycle['id'], task['id'], 0)
        self.assertIn('Fixture draft.', artifact['content'])
        self.assertEqual(artifact['sha256'], metadata['sha256'])
        for cycle_id, task_id, index in ((cycle['id'], task['id'], -1),
                                        (cycle['id'], task['id'], True),
                                        ('../outside', task['id'], 0),
                                        (cycle['id'], '../../README.md', 0)):
            with self.subTest(cycle_id=cycle_id, task_id=task_id, index=index):
                with self.assertRaises(ValueError):
                    self.engine.get_artifact(cycle_id, task_id, index)
        (self.root / metadata['path']).write_text('Bytes changed after the recorded execution.', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.engine.get_artifact(cycle['id'], task['id'], 0)
        with self.assertRaises(ValueError):
            self.engine.start('review', cycle_id=cycle['id'], task_id=task['id'],
                              payload={'accepted': True, 'note': 'A stale review cannot accept changed bytes.'})
        saved_task = self.engine.state()['cycles'][0]['tasks'][0]
        self.assertEqual(saved_task['status'], 'needs_review')


if __name__ == '__main__':
    unittest.main()
