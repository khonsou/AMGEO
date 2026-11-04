"""HTTP integration for the executable workflow, without live agents or providers."""
import copy
import http.client
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

from am_seo.server import make_server
from am_seo.workflow import WorkflowEngine


class ApiFixtureRunner:
    def __init__(self):
        self.calls = []
        self.entered = None
        self.release = None
        self.tasks = [{
            'title': 'Prepare the evidence-based bilingual explanation',
            'channel': 'owned', 'market': 'both', 'owner': 'agent', 'kind': 'content',
            'instruction': 'Write a local draft with the source and publication scope.',
            'acceptance': ['Include source and unpublished scope'], 'dependencies': [],
            'evidence_urls': ['https://example.org/product'], 'requires': [],
        }]

    def __call__(self, prompt, schema, output_dir, search=True):
        self.calls.append({'prompt': prompt, 'schema': schema, 'output_dir': Path(output_dir)})
        if self.entered:
            self.entered.set()
        if self.release and not self.release.wait(timeout=5):
            raise RuntimeError('Fixture gate timed out')
        if schema.get('title') == 'AMSEOExecution':
            result = {
                'summary': 'Prepared a real fixture draft in the temporary project.',
                'deliverables': [{'title': 'Fixture explanation',
                                  'content': 'Fixture text <script>must remain text</script>\n'
                                             'Source: https://example.org/product\nUnpublished local draft.'}],
                'evidence_urls': ['https://example.org/product'],
                'acceptance_checks': [{'criterion': 'Include source and unpublished scope',
                                       'passed': True, 'detail': 'Both are included in the draft.'}],
            }
        else:
            result = {
                'summary': 'Fixture evidence produced actual executable tasks.',
                'findings': [{'id': 'F1', 'title': 'Explain supported mechanisms',
                              'detail': 'Keep source-backed content distinct from measured performance.',
                              'evidence_urls': ['https://example.org/product'], 'source_date': '2026-10-29'}],
                'tasks': copy.deepcopy(self.tasks),
            }
        return {'result': result, 'trace': {'runtime': 'offline-api-fixture'}}


class WorkflowApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='am-seo-workflow-api-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.write_json('config/project.json', {'name': 'AM SEO', 'brand': {'name': 'Angry Miao'}})
        self.write_json('config/upstreams.lock.json', {'upstreams': []})
        self.write_json('outputs/agent-kit/tasks.json', {'tasks': []})
        self.write_json('outputs/agent-kit/capabilities.json', {})
        self.write_json('outputs/agent-kit/product-facts.json', {'facts': []})
        self.write_json('outputs/agent-kit/query-seeds.json', {'queries': []})
        shutil.copy2(ROOT / 'outputs/agent-kit/score_observations.py',
                     self.root / 'outputs/agent-kit/score_observations.py')
        self.no_live_agent = mock.patch('am_seo.workflow.CodexRunner.__call__',
                                        side_effect=AssertionError('Live providers are forbidden in this test'))
        self.live_agent_mock = self.no_live_agent.start()
        self.addCleanup(self.no_live_agent.stop)
        self.addCleanup(self.assert_no_live_calls)
        self.runner = ApiFixtureRunner()
        self.engine = WorkflowEngine(self.root, runner=self.runner)
        self.server = make_server(self.root, host='127.0.0.1', port=0)
        self.server.workflow = self.engine
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        status, state, _ = self.call('GET', '/api/state')
        self.assertEqual(status, 200)
        self.token = state['csrf_token']

    def assert_no_live_calls(self):
        self.live_agent_mock.assert_not_called()

    def stop(self):
        if self.runner.release:
            self.runner.release.set()
        if self.engine.thread:
            self.engine.thread.join(timeout=5)
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def write_json(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    def call(self, method, path, payload=None, *, token=True, headers=None):
        body = None
        request_headers = {}
        if payload is not None:
            body = json.dumps(payload).encode('utf-8')
            request_headers['Content-Type'] = 'application/json'
        if method == 'POST' and token:
            request_headers['X-AMSEO-Token'] = getattr(self, 'token', '')
        request_headers.update(headers or {})
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            data = response.read()
            value = json.loads(data) if 'application/json' in response.getheader('Content-Type', '') else data.decode()
            return response.status, value, dict(response.getheaders())
        finally:
            connection.close()

    def wait_cycle(self, identifier):
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            status, state, _ = self.call('GET', '/api/state')
            self.assertEqual(status, 200)
            if not state['workflow']['active']:
                cycle = next(c for c in state['workflow']['cycles'] if c['id'] == identifier)
                return cycle
            time.sleep(.01)
        self.fail('Offline API workflow did not complete')

    def analyze(self):
        status, result, _ = self.call('POST', '/api/workflow', {
            'action': 'analyze', 'goal': 'Create actionable bilingual improvements',
            'market': 'both', 'channels': ['search', 'ai', 'owned']})
        self.assertEqual(status, 202, result)
        cycle = self.wait_cycle(result['cycle']['id'])
        self.assertNotEqual(cycle['status'], 'failed', cycle.get('error'))
        return cycle

    def execute(self, cycle):
        status, result, _ = self.call('POST', '/api/workflow', {
            'action': 'execute', 'cycle_id': cycle['id'], 'task_id': cycle['tasks'][0]['id']})
        self.assertEqual(status, 202, result)
        return self.wait_cycle(cycle['id'])

    def test_state_exposes_an_executable_workflow_without_calling_a_provider(self):
        status, state, _ = self.call('GET', '/api/state')
        self.assertEqual(status, 200)
        self.assertEqual(state['workflow']['cycles'], [])
        self.assertFalse(state['workflow']['active'])
        self.assertTrue(state['workflow']['runtime']['available'])
        self.assertEqual(self.runner.calls, [])

    def test_current_chat_agent_can_submit_actual_outputs_without_a_backend_model_call(self):
        cycle = self.analyze()
        task = cycle['tasks'][0]
        payload = {'action': 'submit-result', 'cycle_id': cycle['id'], 'task_id': task['id'],
                   'executor': 'current_chat_agent', 'result': {
                       'summary': 'Actual external agent output in this temporary project.',
                       'deliverables': [{'title': 'External artifact', 'content': 'Source https://example.org/product; unpublished.'}],
                       'evidence_urls': ['https://example.org/product'],
                       'acceptance_checks': [{'criterion': task['acceptance'][0], 'passed': True, 'detail': 'Source and scope included.'}]}}
        self.engine.data['runtime_block'] = {'kind': 'usage_limit', 'message': 'Fixture quota'}
        status, result, _ = self.call('POST', '/api/workflow', {**payload, 'executor': 'unapproved-new-executor'})
        self.assertEqual(status, 400)
        status, result, _ = self.call('POST', '/api/workflow', payload)
        self.assertEqual(status, 202, result)
        submitted = result['cycle']['tasks'][0]
        self.assertEqual(submitted['status'], 'needs_review')
        self.assertFalse(submitted['structural_validation']['factual_truth_verified'])
        self.assertTrue((self.root / submitted['deliverables'][0]['path']).exists())
        self.assertEqual(len(self.runner.calls), 1, 'Only the earlier fixture analysis called a runner')

    def test_analyze_execute_artifact_and_review_work_through_the_http_api(self):
        cycle = self.analyze()
        task = cycle['tasks'][0]
        self.assertEqual(task['status'], 'ready')
        self.assertEqual(task['owner'], 'agent')
        self.assertTrue(task['acceptance'])
        self.assertEqual(self.call('GET', '/api/state')[1]['requests'], [],
                         'Analysis must execute, not only append a waiting request')
        cycle = self.execute(cycle)
        task = cycle['tasks'][0]
        self.assertEqual(task['status'], 'needs_review')
        metadata = task['deliverables'][0]
        self.assertTrue((self.root / metadata['path']).is_file())
        self.assertNotIn('content', metadata)
        artifact_url = f'/api/workflow/artifacts/{cycle["id"]}/{task["id"]}/0'
        status, artifact, headers = self.call('GET', artifact_url)
        self.assertEqual(status, 200, artifact)
        self.assertIn('<script>must remain text</script>', artifact['content'])
        self.assertEqual(artifact['sha256'], metadata['sha256'])
        self.assertIn('application/json', headers['Content-Type'])
        status, result, _ = self.call('POST', '/api/workflow', {
            'action': 'review', 'cycle_id': cycle['id'], 'task_id': task['id'],
            'accepted': True, 'note': 'Reviewed the current source-backed local draft.'})
        self.assertEqual(status, 202, result)
        reviewed = result['cycle']['tasks'][0]
        self.assertEqual(reviewed['status'], 'completed')
        self.assertEqual(reviewed['completion_scope'], 'reviewed_local_artifact')
        self.assertIn('current source-backed', reviewed['review']['note'])
        self.assertEqual(len(self.runner.calls), 2)

    def test_write_guards_and_invalid_actions_do_not_launch_an_agent(self):
        payload = {'action': 'analyze', 'goal': 'This must not run without authorization'}
        status, _, _ = self.call('POST', '/api/workflow', payload, token=False)
        self.assertEqual(status, 403)
        status, _, _ = self.call('POST', '/api/workflow', payload,
                                 headers={'Origin': 'https://attacker.invalid'})
        self.assertEqual(status, 403)
        for invalid in ({}, {'action': ['analyze']}, {'action': 'shell'},
                        {'action': 'execute', 'cycle_id': '../outside'},
                        {'action': 'evaluate', 'cycle_id': 'missing'}):
            with self.subTest(invalid=invalid):
                status, result, _ = self.call('POST', '/api/workflow', invalid)
                self.assertEqual(status, 400, result)
        self.assertEqual(self.runner.calls, [])
        self.assertEqual(self.call('GET', '/api/state')[1]['workflow']['cycles'], [])

    def test_artifact_traversal_invalid_indices_and_changed_bytes_are_refused(self):
        cycle = self.execute(self.analyze())
        task = cycle['tasks'][0]
        for suffix in ('../../README.md/0', f'{task["id"]}/-1', f'{task["id"]}/NaN',
                       f'{task["id"]}/99', '%2e%2e%2fREADME.md/0'):
            with self.subTest(suffix=suffix):
                status, _, _ = self.call('GET', f'/api/workflow/artifacts/{cycle["id"]}/{suffix}')
                self.assertIn(status, (400, 404))
        metadata = task['deliverables'][0]
        (self.root / metadata['path']).write_text('Changed after the original hash was recorded.')
        status, _, _ = self.call('GET', f'/api/workflow/artifacts/{cycle["id"]}/{task["id"]}/0')
        self.assertEqual(status, 404)
        status, result, _ = self.call('POST', '/api/workflow', {
            'action': 'review', 'cycle_id': cycle['id'], 'task_id': task['id'],
            'accepted': True, 'note': 'This stale artifact must not be accepted.'})
        self.assertEqual(status, 400, result)
        self.assertEqual(self.wait_cycle(cycle['id'])['tasks'][0]['status'], 'needs_review')

    def test_human_result_and_explicit_review_remain_distinct_http_steps(self):
        self.runner.tasks[0].update(owner='human', kind='decision',
                                    title='Confirm the brand decision', requires=['brand_decision'])
        cycle = self.analyze()
        task = cycle['tasks'][0]
        status, result, _ = self.call('POST', '/api/workflow', {
            'action': 'handoff', 'cycle_id': cycle['id'], 'task_id': task['id'],
            'result': 'The brand team supplied a model-specific decision.',
            'evidence_urls': ['https://example.org/product']})
        self.assertEqual(status, 202, result)
        submitted = result['cycle']['tasks'][0]
        self.assertEqual(submitted['status'], 'submitted_review')
        self.assertEqual(submitted['submitted_result']['evidence_urls'], ['https://example.org/product'])
        status, result, _ = self.call('POST', '/api/workflow', {
            'action': 'review', 'cycle_id': cycle['id'], 'task_id': task['id'],
            'accepted': True, 'note': 'The supplied decision was checked against the source.'})
        self.assertEqual(status, 202, result)
        self.assertEqual(result['cycle']['tasks'][0]['status'], 'completed')
        self.assertEqual(len(self.runner.calls), 1)

    def test_concurrent_analysis_returns_conflict_without_duplicating_a_cycle(self):
        self.runner.entered, self.runner.release = threading.Event(), threading.Event()
        status, first, _ = self.call('POST', '/api/workflow', {'action': 'analyze'})
        self.assertEqual(status, 202)
        self.assertTrue(self.runner.entered.wait(timeout=2))
        status, result, _ = self.call('POST', '/api/workflow', {'action': 'analyze'})
        self.assertEqual(status, 409, result)
        self.runner.release.set()
        self.wait_cycle(first['cycle']['id'])
        workflow = self.call('GET', '/api/state')[1]['workflow']
        self.assertEqual(len(workflow['cycles']), 1)
        self.assertEqual(len(self.runner.calls), 1)


if __name__ == '__main__':
    unittest.main()
