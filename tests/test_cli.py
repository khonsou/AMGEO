"""Black-box CLI contract tests in an isolated temporary project copy."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProjectCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='am-seo-cli-')
        self.addCleanup(self.temporary.cleanup)
        self.fixture = (Path(self.temporary.name) / 'project').resolve()
        self.fixture.mkdir()
        for directory in ('src', 'config'):
            shutil.copytree(ROOT / directory, self.fixture / directory,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copy2(ROOT / 'am-seo', self.fixture / 'am-seo')
        shutil.copytree(ROOT / 'outputs' / 'agent-kit', self.fixture / 'outputs' / 'agent-kit',
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        (self.fixture / 'scripts').mkdir()
        shutil.copy2(ROOT / 'scripts' / 'sync_upstreams.py', self.fixture / 'scripts' / 'sync_upstreams.py')
        self.foreign_cwd = Path(self.temporary.name) / 'unrelated-working-directory'
        self.foreign_cwd.mkdir()

    def invoke(self, *arguments):
        return subprocess.run([sys.executable, str(self.fixture / 'am-seo'), *map(str, arguments)],
                              cwd=self.foreign_cwd, text=True, capture_output=True, timeout=30,
                              env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})

    def test_status_from_foreign_cwd_reads_the_project_task_contract(self):
        completed = self.invoke('status', '--json')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        contract = json.loads((self.fixture / 'outputs' / 'agent-kit' / 'tasks.json').read_text(encoding='utf-8'))
        self.assertEqual(result['project_root'], str(self.fixture))
        self.assertEqual(result['task_count'], len(contract['tasks']))
        self.assertEqual(sum(result['counts'].values()), result['task_count'])
        self.assertEqual({task['id'] for task in result['tasks']}, {task['id'] for task in contract['tasks']})
        self.assertFalse((self.foreign_cwd / 'outputs').exists())

    def test_doctor_missing_upstreams_or_connections_are_nonfatal_and_offline(self):
        # No vendor checkouts are copied. This is a meaningful fresh-checkout case.
        completed = self.invoke('doctor', '--json')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result['project_root'], str(self.fixture))
        self.assertEqual(result['status'], 'offline_ready_pending_connections')
        self.assertEqual(result['provider_calls'], 0)
        self.assertFalse(result['credentials_inspected'])
        self.assertFalse(result['upstream_code_executed'])
        upstreams = result['upstreams']['repositories']
        self.assertTrue(upstreams)
        self.assertTrue(all(repo['status'] == 'pending' for repo in upstreams))

    def test_offline_run_validates_only_the_temporary_copy_and_records_scope(self):
        metrics_path = self.fixture / 'outputs' / 'agent-kit' / 'geo-metrics.json'
        metrics_before = metrics_path.read_bytes()
        completed = self.invoke('run', '--offline')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        report_path = self.fixture / 'outputs' / 'project-status.json'
        report = json.loads(report_path.read_text(encoding='utf-8'))
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(report['execution_mode'], 'offline')
        self.assertEqual(report['validation']['operations'], 13)
        self.assertTrue(report['validation']['rollback_roundtrip'])
        self.assertEqual(report['deployment_status'], 'not_deployed_by_this_run')
        self.assertEqual(report['production_writes_performed'], 0)
        self.assertEqual(report['provider_calls_performed'], 0)
        self.assertFalse(report['upstream_code_executed'])
        self.assertFalse(report['live_geo_baseline_measured'])
        self.assertEqual(metrics_path.read_bytes(), metrics_before)
        self.assertFalse((self.foreign_cwd / 'outputs').exists())

    def test_score_accepts_absolute_temporary_paths_and_empty_evidence_stays_not_run(self):
        input_path = self.foreign_cwd / 'empty-fixture.jsonl'
        output_path = self.foreign_cwd / 'nested' / 'metrics.json'
        input_path.write_text('', encoding='utf-8')
        completed = self.invoke('score', input_path, output_path)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(output_path.read_text(encoding='utf-8'))
        self.assertEqual(result['status'], 'not_run')
        self.assertEqual(result['observation_count'], 0)
        self.assertEqual(result['groups'], [])

    def test_score_relative_paths_are_project_relative_from_foreign_cwd(self):
        input_path = self.fixture / 'fixture.jsonl'
        input_path.write_text('', encoding='utf-8')
        completed = self.invoke('score', 'fixture.jsonl', 'scratch/metrics.json')
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads((self.fixture / 'scratch' / 'metrics.json').read_text())['status'], 'not_run')
        self.assertFalse((self.foreign_cwd / 'scratch').exists())

    def test_score_refuses_to_overwrite_the_observation_input(self):
        input_path = self.foreign_cwd / 'same-file.jsonl'
        original = b'unit fixture whose bytes must not be overwritten\n'
        input_path.write_bytes(original)
        completed = self.invoke('score', input_path, input_path)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('different files', completed.stderr)
        self.assertEqual(input_path.read_bytes(), original)

    def test_score_propagates_failure_for_duplicate_observations(self):
        record = {'run_id': 'unit-fixture', 'query_id': 'fixture-question', 'surface': 'consumer',
                  'platform': 'unit-fixture-platform', 'locale': 'zh-CN', 'mode': 'web-search',
                  'status': 'no_ai_answer'}
        input_path = self.foreign_cwd / 'duplicate-fixture.jsonl'
        output_path = self.foreign_cwd / 'rejected-metrics.json'
        line = json.dumps(record)
        input_path.write_text(line + '\n' + line + '\n', encoding='utf-8')
        completed = self.invoke('score', input_path, output_path)
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('Duplicate', completed.stderr)
        self.assertFalse(output_path.exists())

    def test_offline_flag_is_required_before_running(self):
        completed = self.invoke('run')
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn('--offline', completed.stderr)
        self.assertFalse((self.fixture / 'outputs' / 'project-status.json').exists())

    def test_deps_verify_propagates_missing_checkout_failure(self):
        # The disposable project deliberately has no vendor tree.
        completed = self.invoke('deps', 'verify')
        self.assertNotEqual(completed.returncode, 0)
        self.assertFalse((self.fixture / 'vendor').exists())


if __name__ == '__main__':
    unittest.main()
