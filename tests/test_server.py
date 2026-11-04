"""Local console API contracts, isolated from project runtime data and providers."""
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from am_seo.server import make_server


class ConsoleServerTests(unittest.TestCase):
    def test_todo_checkbox_and_verification_are_distinct_http_fields(self):
        self.write_json('config/geo-playbook.json', json.loads((ROOT / 'config/geo-playbook.json').read_text()))
        self.call('POST', '/api/geo', {'action': 'generate', 'question_ids': ['find-mouse-zh']})
        self.assertEqual(self.call('POST', '/api/geo', {'action': 'toggle', 'task_id': 'ai-crawlers', 'done': True})[0], 200)
        task = next(t for t in self.call('GET', '/api/state')[1]['geo_workspace']['tasks'] if t['id'] == 'ai-crawlers')
        self.assertTrue(task['execution_done'])
        self.assertEqual(task['validation_status'], 'not_checked')
        self.assertEqual(task['status'], 'ready')

    def test_question_connection_guard_and_public_state_never_return_credential(self):
        from am_seo.credentials import MemoryVault
        self.server.question_lab.vault = MemoryVault()
        credential = 'fixture-provider-credential-not-a-real-key'
        payload = {'action': 'configure', 'provider': 'deepseek', 'model': 'fixture-model', 'api_key': credential}
        self.assertEqual(self.call('POST', '/api/question-lab', payload, token=False)[0], 403)
        status, result, _ = self.call('POST', '/api/question-lab', payload)
        self.assertEqual(status, 200)
        self.assertNotIn(credential, json.dumps(result))
        state = self.call('GET', '/api/state')[1]
        self.assertTrue(state['question_lab']['connection']['has_key'])
        self.assertNotIn(credential, json.dumps(state))

    def test_geo_api_materializes_hash_checked_pages_and_rejects_unguarded_writes(self):
        self.write_json('config/geo-playbook.json', json.loads((ROOT / 'config/geo-playbook.json').read_text()))
        question_id = 'find-mouse-zh'
        status, _, _ = self.call('POST', '/api/geo', {'action': 'generate', 'question_ids': [question_id]}, token=False)
        self.assertEqual(status, 403)
        self.assertEqual(self.server.geo_workspace.state()['tasks'], [])
        status, _, _ = self.call('POST', '/api/geo', {'action': 'generate', 'question_ids': [question_id]})
        self.assertEqual(status, 200)
        task_id = 'page-' + question_id
        status, response, _ = self.call('POST', '/api/geo', {'action': 'prepare', 'task_id': task_id})
        self.assertEqual(status, 200)
        self.assertEqual(response['result']['completion_scope'], 'local_artifact_not_published')
        status, page, headers = self.call('GET', '/api/geo/files/' + task_id + '/index.html')
        self.assertEqual(status, 200)
        self.assertIn('id="tool"', page)
        self.assertIn("script-src 'self'", headers['Content-Security-Policy'])
        self.assertEqual(self.call('GET', '/api/geo/files/' + task_id + '/../../README.md')[0], 404)
        self.assertEqual(self.call('POST', '/api/geo', {'action': 'publish', 'task_id': task_id})[0], 400)

    def test_geo_traffic_errors_do_not_overwrite_existing_aggregate(self):
        payload = {'action': 'import-traffic', 'csv': 'source,sessions\nchatgpt.com,4\n', 'start_date': '2026-11-01', 'end_date': '2026-11-03', 'property_host': 'store.angrymiao.com'}
        self.assertEqual(self.call('POST', '/api/geo', payload)[0], 200)
        bad = {**payload, 'csv': 'source,sessions,email\nchatgpt.com,4,private@example.test\n'}
        self.assertEqual(self.call('POST', '/api/geo', bad)[0], 400)
        report = self.call('GET', '/api/state')[1]['geo_workspace']['traffic']
        self.assertEqual(report['ai_sessions'], 4)
        self.assertNotIn('csv', report)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='am-seo-console-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.write_json('config/project.json', {'name': 'AM SEO', 'brand': {'name': 'Angry Miao'}})
        self.write_json('config/upstreams.lock.json', {'upstreams': []})
        self.write_json('outputs/agent-kit/tasks.json', {
            'tasks': [{'id': 'A01', 'status': 'completed', 'action': 'Fixture artifact check'}]})
        self.write_json('outputs/agent-kit/capabilities.json', {'production_publish_scope': 'not_established'})
        self.write_json('outputs/agent-kit/product-facts.json', {'facts': []})
        (self.root / 'README.md').write_text('Fixture readme <script>not executable</script>', encoding='utf-8')
        # A real child process, with fixed commands observable in this disposable project.
        (self.root / 'am-seo').write_text(
            '#!/usr/bin/env python3\n'
            'import json, pathlib, sys, time\n'
            'root = pathlib.Path(__file__).resolve().parent\n'
            'with (root / "job-arguments.jsonl").open("a") as stream:\n'
            '    stream.write(json.dumps(sys.argv[1:]) + "\\n")\n'
            'deadline = time.monotonic() + 8\n'
            'while (root / "hold-job").exists() and time.monotonic() < deadline:\n'
            '    time.sleep(0.02)\n'
            'print("fixture command: " + json.dumps(sys.argv[1:]), flush=True)\n'
            'sys.exit(7 if sys.argv[1:] == ["deps", "verify"] else 0)\n', encoding='utf-8')
        (self.root / 'am-seo').chmod(0o755)
        self.server = None
        self.thread = None
        self.addCleanup(self.stop_server)
        self.start_server()

    def write_json(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding='utf-8')

    def start_server(self):
        self.server = make_server(self.root, host='127.0.0.1', port=0)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.token = self.call('GET', '/api/state')[1]['csrf_token']

    def stop_server(self):
        (self.root / 'hold-job').unlink(missing_ok=True)
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=3)
            self.server = None

    def call(self, method, path, payload=None, *, headers=None, token=True, raw=None):
        request_headers = {}
        body = raw
        if payload is not None:
            body = json.dumps(payload).encode('utf-8')
            request_headers['Content-Type'] = 'application/json'
        if method == 'POST' and token:
            request_headers['X-AMSEO-Token'] = self.token
        request_headers.update(headers or {})
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=request_headers)
            response = connection.getresponse()
            data = response.read()
            content_type = response.getheader('Content-Type', '')
            value = json.loads(data) if 'application/json' in content_type else data.decode('utf-8')
            return response.status, value, dict(response.getheaders())
        finally:
            connection.close()

    def wait_job(self, job_id):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            jobs = self.call('GET', '/api/state')[1]['jobs']
            job = next(item for item in jobs if item['id'] == job_id)
            if job['status'] in ('succeeded', 'failed'):
                return job
            time.sleep(0.03)
        self.fail('fixture subprocess did not reach a terminal job status')

    def test_health_and_state_expose_actual_contract_without_invented_metrics(self):
        status, health, _ = self.call('GET', '/api/health')
        self.assertEqual(status, 200)
        self.assertEqual(health, {'status': 'ok', 'project': 'AM SEO'})
        status, state, _ = self.call('GET', '/api/state')
        self.assertEqual(status, 200)
        self.assertEqual(state['project']['brand']['name'], 'Angry Miao')
        self.assertEqual(state['tasks'][0]['id'], 'A01')
        self.assertEqual(state['task_counts']['completed'], 1)
        self.assertIsNone(state['validation'])
        self.assertIsNone(state['run_report'])
        self.assertEqual(state['requests'], [])
        self.assertEqual(state['jobs'], [])
        self.assertTrue(state['csrf_token'])

    def test_artifacts_are_allowlisted_text_and_path_traversal_is_rejected(self):
        status, artifact, _ = self.call('GET', '/api/artifacts/readme')
        self.assertEqual(status, 200)
        self.assertEqual(artifact['id'], 'readme')
        self.assertIn('<script>not executable</script>', artifact['content'])
        for path in ('/api/artifacts/unknown', '/api/artifacts/../../config/project.json',
                     '/api/artifacts/%2e%2e%2f%2e%2e%2fconfig%2fproject.json'):
            with self.subTest(path=path):
                status, _, _ = self.call('GET', path)
                self.assertIn(status, (400, 404))

    def test_host_origin_and_token_guards_prevent_cross_site_mutations(self):
        payload = {'goal': 'Inspect evidence', 'market': 'both', 'channels': ['search']}
        status, _, _ = self.call('GET', '/api/state', headers={'Host': 'attacker.invalid'})
        self.assertEqual(status, 403)
        status, _, _ = self.call('POST', '/api/requests', payload, token=False)
        self.assertEqual(status, 403)
        status, _, _ = self.call('POST', '/api/requests', payload,
                                 headers={'X-AMSEO-Token': 'wrong-token'})
        self.assertEqual(status, 403)
        status, _, _ = self.call('POST', '/api/requests', payload,
                                 headers={'Origin': 'https://attacker.invalid'})
        self.assertEqual(status, 403)
        self.assertEqual(self.call('GET', '/api/state')[1]['requests'], [])
        status, result, _ = self.call('POST', '/api/requests', payload,
                                      headers={'Origin': f'http://127.0.0.1:{self.port}'})
        self.assertEqual(status, 201)
        self.assertEqual(result['request']['status'], 'waiting_executor')

    def test_request_and_feedback_persist_without_changing_task_completion(self):
        task_path = self.root / 'outputs/agent-kit/tasks.json'
        original_tasks = task_path.read_bytes()
        payload = {'goal': 'Audit Chinese and English brand citations', 'market': 'both',
                   'channels': ['ai', 'reviews']}
        status, result, _ = self.call('POST', '/api/requests', payload)
        self.assertEqual(status, 201)
        request_id = result['request']['id']
        self.assertEqual(result['request']['status'], 'waiting_executor')
        status, result, _ = self.call('POST', '/api/feedback', {'task_id': 'A01', 'text': 'Keep source dates explicit.'})
        self.assertEqual(status, 201)
        feedback_id = result['feedback']['id']
        self.assertEqual(result['feedback']['status'], 'recorded')
        self.stop_server()
        self.start_server()
        state = self.call('GET', '/api/state')[1]
        self.assertEqual(state['requests'][0]['id'], request_id)
        self.assertEqual(state['requests'][0]['goal'], payload['goal'])
        self.assertEqual(state['feedback'][0]['id'], feedback_id)
        self.assertEqual(task_path.read_bytes(), original_tasks)
        self.assertTrue((self.root / 'outputs/runtime/console/requests.json').is_file())

    def test_invalid_request_fields_and_unknown_feedback_task_are_rejected(self):
        payload = {'goal': 'Audit evidence', 'market': 'both', 'channels': ['search']}
        for change in ({'goal': ''}, {'goal': []}, {'market': 'unsupported'}, {'market': []},
                       {'market': {}}, {'channels': ['shell']}, {'channels': []}, {'channels': [{}]}):
            with self.subTest(change=change):
                status, _, _ = self.call('POST', '/api/requests', {**payload, **change})
                self.assertEqual(status, 400)
        status, _, _ = self.call('POST', '/api/feedback', {'task_id': 'A99', 'text': 'Unsupported task'})
        self.assertEqual(status, 400)
        state = self.call('GET', '/api/state')[1]
        self.assertEqual(state['requests'], [])
        self.assertEqual(state['feedback'], [])
        for malformed_kind in ([], {}, None):
            with self.subTest(kind=malformed_kind):
                self.assertEqual(self.call('POST', '/api/jobs', {'kind': malformed_kind})[0], 400)
        self.assertEqual(self.call('POST', '/api/feedback', {'task_id': [], 'text': 'Malformed task'})[0], 400)

    def test_json_and_body_limits_fail_before_recording_a_request(self):
        status, _, _ = self.call('POST', '/api/requests', raw=b'{}',
                                 headers={'Content-Type': 'text/plain'})
        self.assertIn(status, (400, 415))
        status, _, _ = self.call('POST', '/api/requests', raw=b'{broken',
                                 headers={'Content-Type': 'application/json'})
        self.assertEqual(status, 400)
        status, _, _ = self.call('POST', '/api/requests', raw=b'[]',
                                 headers={'Content-Type': 'application/json'})
        self.assertEqual(status, 400)
        status, _, _ = self.call('POST', '/api/requests', raw=b' ' * (32768 + 1),
                                 headers={'Content-Type': 'application/json'})
        self.assertEqual(status, 413)
        self.assertEqual(self.call('GET', '/api/state')[1]['requests'], [])

    def test_jobs_run_only_fixed_commands_and_preserve_real_exit_status(self):
        status, result, _ = self.call('POST', '/api/jobs', {'kind': 'offline-validation'})
        self.assertEqual(status, 202)
        success = self.wait_job(result['job']['id'])
        self.assertEqual(success['status'], 'succeeded')
        self.assertIn('fixture command', success['output'])
        self.assertTrue(success['finished_at'])
        status, result, _ = self.call('POST', '/api/jobs', {'kind': 'upstream-verification'})
        self.assertEqual(status, 202)
        failure = self.wait_job(result['job']['id'])
        self.assertEqual(failure['status'], 'failed')
        arguments = [json.loads(line) for line in (self.root / 'job-arguments.jsonl').read_text().splitlines()]
        self.assertEqual(arguments, [['run', '--offline'], ['deps', 'verify']])
        self.stop_server()
        self.start_server()
        self.assertEqual({job['status'] for job in self.call('GET', '/api/state')[1]['jobs']},
                         {'succeeded', 'failed'})

    def test_concurrent_job_requests_do_not_spawn_duplicate_work(self):
        gate = self.root / 'hold-job'
        gate.touch()
        status, first, _ = self.call('POST', '/api/jobs', {'kind': 'offline-validation'})
        self.assertEqual(status, 202)
        status, conflict, _ = self.call('POST', '/api/jobs', {'kind': 'upstream-verification'})
        self.assertEqual(status, 409)
        self.assertEqual(conflict['job']['id'], first['job']['id'])
        gate.unlink()
        self.assertEqual(self.wait_job(first['job']['id'])['status'], 'succeeded')
        self.assertEqual(len((self.root / 'job-arguments.jsonl').read_text().splitlines()), 1)

    def test_goal_text_is_stored_as_data_and_cannot_select_a_shell_command(self):
        marker = self.root / 'must-not-exist'
        goal = f'$(touch {marker}); inspect brand evidence'
        status, result, _ = self.call('POST', '/api/requests', {
            'goal': goal, 'market': 'zh-CN', 'channels': ['owned']})
        self.assertEqual(status, 201)
        self.assertEqual(result['request']['goal'], goal)
        self.assertFalse(marker.exists())
        status, _, _ = self.call('POST', '/api/jobs', {'kind': f'offline-validation; touch {marker}'})
        self.assertEqual(status, 400)
        self.assertFalse((self.root / 'job-arguments.jsonl').exists())
        self.assertFalse(marker.exists())

    def test_server_rejects_a_network_wide_bind(self):
        with self.assertRaises(ValueError):
            make_server(self.root, host='0.0.0.0', port=0)


if __name__ == '__main__':
    unittest.main()
