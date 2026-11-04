import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from am_seo.credentials import MemoryVault
from am_seo.geo_workspace import GeoWorkspace
from am_seo.question_lab import QuestionLab, CompatibleClient, NoRedirect, ProviderError, normalize_panel, summarize, classify_answer, validate_endpoint


def questions():
    result = []
    for locale in ('zh-CN', 'en-US'):
        for intent in ('find', 'alternatives', 'how', 'facts'):
            prompt = f'{locale} {intent}: Which product fits this workflow?'
            if intent == 'facts': prompt = f'{locale}: What does AM Infinity Mouse support?'
            result.append({'locale': locale, 'intent': intent, 'product_line': 'mouse' if intent in {'find', 'facts'} else 'ai_device', 'prompt': prompt})
    return {'questions': result}


class FakeClient:
    def __init__(self, connection, key, calls, hard=False): self.calls, self.hard, self.key = calls, hard, key
    def models(self): return ['fixture-model']
    def complete(self, messages, *, json_output=False):
        self.calls.append({'messages': messages, 'json_output': json_output})
        if json_output: return {'text': json.dumps(questions()), 'returned_model': 'fixture-model-1', 'usage': {}}
        if self.hard: raise ProviderError('authentication rejected ' + self.key, hard=True)
        prompt = messages[-1]['content']
        return {'text': 'Angry Miao / CYBERBOARD R6' if 'facts' not in prompt else 'A generic response.', 'returned_model': 'fixture-model-1', 'usage': {'total_tokens': 3}}


class QuestionLabTests(unittest.TestCase):
    def test_active_credential_is_rejected_from_product_and_model_list_substrings(self):
        with self.assertRaises(ValueError): self.lab.start('generate-test', {'product': 'public ' + self.key})
        self.assertEqual(self.calls, [])
        client = CompatibleClient({'base_url': 'https://api.deepseek.com/v1', 'model': 'fixture-model'}, self.key)
        client.request = lambda *args: {'data': [{'id': 'echo/' + self.key}, {'id': 'fixture-model'}]}
        self.assertEqual(client.models(), ['fixture-model'])

    def test_failed_persistent_rotation_cannot_send_old_key_to_new_provider(self):
        class FallbackVault(MemoryVault):
            def __init__(self): self.value = 'persisted-original-key'
            def set(self, value): self.value = value
        vault = FallbackVault()
        self.lab.vault = vault
        self.lab.configure({'provider': 'openai', 'model': 'fixture-model', 'api_key': 'replacement-memory-only-key'})
        restored = QuestionLab(self.root, self.workspace, vault=FallbackVault(), client_factory=lambda *args: self.fail('must not forward the stale key'))
        self.assertFalse(restored.state()['connection']['has_key'])
        with self.assertRaises(ValueError): restored.verify_connection()

    def test_malformed_usage_records_error_and_stops_instead_of_abandoning_job(self):
        client = CompatibleClient({'provider': 'deepseek', 'base_url': 'https://api.deepseek.com/v1', 'model': 'fixture-model'}, self.key)
        def response(path, payload):
            if payload.get('response_format'):return {'choices': [{'message': {'content': json.dumps(questions())}}], 'model': 'fixture-model'}
            return {'choices': [{'message': {'content': 'A generic answer.'}}], 'usage': ['invalid']}
        client.request = response;self.lab.factory = lambda *args: client
        state = self.run_job('generate-test')
        self.assertEqual(state['job']['status'], 'partial')
        self.assertEqual(state['runs'][0]['observations'][0]['status'], 'error')
        self.assertFalse(any(r['status']=='running' for r in state['runs'][0]['observations']))
        self.assertEqual(sum(r['status']=='not_run' for r in state['runs'][0]['observations']), 7)

    def test_normalization_enforces_both_product_lines_per_language(self):
        value = questions()
        for q in value['questions']: q['product_line'] = 'mouse'
        with self.assertRaises(ValueError): normalize_panel(value)
        value = questions();value['questions'][0]['locale'] = ['zh-CN']
        with self.assertRaises(ValueError): normalize_panel(value)

    def test_discovery_misses_create_evidence_linked_todos_automatically(self):
        class MissingClient(FakeClient):
            def complete(self, messages, *, json_output=False):
                result = super().complete(messages, json_output=json_output)
                if not json_output: result['text'] = 'A generic answer without a target brand.'
                return result
        self.lab.factory = lambda connection, key: MissingClient(connection, key, self.calls)
        state = self.run_job('generate-test')
        tasks = [t for t in self.workspace.state()['tasks'] if t['kind']=='page']
        self.assertEqual(len(tasks), 8)
        self.assertTrue(all(t['test_evidence']['run_id']==state['runs'][0]['id'] for t in tasks))
        self.assertEqual({t['question']['intent'] for t in tasks}, {'find','how','facts','alternatives'})

    def test_malformed_content_is_error_while_real_empty_content_remains_no_answer(self):
        client = CompatibleClient({'provider':'deepseek','base_url':'https://api.deepseek.com/v1','model':'fixture-model'},self.key)
        for content in (0, False, [], {}):
            client.request=lambda *args, value=content:{'choices':[{'message':{'content':value}}]}
            with self.assertRaises(ProviderError):client.complete([{'role':'user','content':'question'}])
        for content in ('', None):
            client.request=lambda *args, value=content:{'choices':[{'message':{'content':value}}]}
            self.assertEqual(client.complete([{'role':'user','content':'question'}])['text'],'')

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='am-question-lab-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / 'config').mkdir()
        (self.root / 'config/geo-playbook.json').write_text((ROOT / 'config/geo-playbook.json').read_text())
        skill = self.root / 'skills/geo-question-eval/SKILL.md'
        skill.parent.mkdir(parents=True); skill.write_text((ROOT / 'skills/geo-question-eval/SKILL.md').read_text())
        self.workspace = GeoWorkspace(self.root); self.calls = []; self.vault = MemoryVault()
        self.key = 'fixture-credential-not-a-real-key'
        self.lab = QuestionLab(self.root, self.workspace, vault=self.vault,
                               client_factory=lambda connection, key: FakeClient(connection, key, self.calls))
        self.lab.configure({'provider': 'deepseek', 'model': 'fixture-model', 'api_key': self.key})

    def run_job(self, action):
        self.lab.start(action, {'product': 'Angry Miao mouse and AI device'})
        self.lab.thread.join(timeout=4)
        self.assertFalse(self.lab.active())
        return self.lab.state()

    def test_full_skill_run_isolated_answers_and_retained_evidence(self):
        state = self.run_job('generate-test')
        self.assertEqual(state['job']['status'], 'completed')
        self.assertEqual(len(self.calls), 9)
        panel, run = state['panel'], state['runs'][0]
        self.assertEqual(len(run['observations']), 8)
        self.assertEqual(len(run['groups']), 4)
        self.assertEqual({g['test_group'] for g in run['groups']}, {'branded', 'discovery'})
        for question, call in zip(panel['questions'], self.calls[1:]):
            self.assertEqual(len(call['messages']), 2)
            self.assertEqual(call['messages'][1]['content'], question['prompt'])
            self.assertNotIn('Angry Miao', call['messages'][0]['content'])
            self.assertNotIn('SKILL', call['messages'][0]['content'])
        self.assertEqual(run['protocol']['mode'], 'api-no-search')
        self.assertTrue((self.lab.directory / 'runs' / run['id'] / 'run.json').is_file())
        self.assertEqual(self.workspace.playbook()['panel_id'], panel['id'])

    def test_retest_freezes_question_panel_and_does_not_generate_again(self):
        original = self.run_job('generate-test')
        panel_hash = original['panel']['questions_sha256']; fingerprint = original['runs'][0]['fingerprint']
        state = self.run_job('test')
        self.assertEqual(len(self.calls), 17)
        self.assertEqual(state['panel']['questions_sha256'], panel_hash)
        self.assertEqual(state['runs'][1]['fingerprint'], fingerprint)
        self.assertEqual(sum(c['json_output'] for c in self.calls), 1)

    def test_auth_error_stops_without_retry_and_unattempted_tests_are_not_zeros(self):
        self.lab.factory = lambda connection, key: FakeClient(connection, key, self.calls, hard=True)
        state = self.run_job('generate-test'); run = state['runs'][0]
        self.assertEqual(len(self.calls), 2)
        self.assertEqual(state['job']['status'], 'partial')
        self.assertEqual(sum(r['status'] == 'error' for r in run['observations']), 1)
        self.assertEqual(sum(r['status'] == 'not_run' for r in run['observations']), 7)
        self.assertTrue(all(group['score'] is None for group in run['groups']))
        for path in self.root.rglob('*.json'): self.assertNotIn(self.key, path.read_text())

    def test_configuration_never_serializes_key_and_model_verification_is_real(self):
        self.assertNotIn(self.key, json.dumps(self.lab.state()))
        self.assertNotIn(self.key, self.lab.path.read_text())
        self.assertFalse(self.lab.state()['connection']['verified'])
        self.lab.verify_connection()
        self.assertTrue(self.lab.state()['connection']['verified'])
        self.assertEqual(self.lab.state()['connection']['available_models'], ['fixture-model'])
        self.assertEqual(self.vault.get(), self.key)

    def test_key_cannot_be_reused_for_new_host_without_explicit_new_credential(self):
        with patch('am_seo.question_lab.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('8.8.8.8', 443))]):
            with self.assertRaises(ValueError):
                self.lab.configure({'provider': 'custom', 'base_url': 'https://other.example/v1', 'model': 'fixture-model'})

    def test_no_credential_means_no_job_or_api_call(self):
        lab = QuestionLab(self.root / 'other', self.workspace, vault=MemoryVault(), client_factory=lambda *args: self.fail('must not call provider'))
        with self.assertRaises(ValueError): lab.start('generate-test', {'product': 'mouse'})

    def test_aliases_no_answer_errors_and_branded_groups_are_separate(self):
        self.assertTrue(classify_answer('AMInfinityMouse and CYBERBOARDR6')['hit'])
        self.assertTrue(classify_answer('怒喵')['brand_mentioned'])
        self.assertFalse(classify_answer('Miao is angry about another mouse')['hit'])
        rows = [{'locale': 'zh-CN', 'test_group': 'discovery', 'status': 'completed', 'hit': True},
                {'locale': 'zh-CN', 'test_group': 'discovery', 'status': 'no_ai_answer', 'hit': False},
                {'locale': 'zh-CN', 'test_group': 'discovery', 'status': 'error'},
                {'locale': 'zh-CN', 'test_group': 'branded', 'status': 'completed', 'hit': True}]
        groups = summarize(rows)
        self.assertEqual(groups[0]['score'], 50)
        self.assertEqual(groups[0]['successful_tests'], 2)
        self.assertEqual(groups[0]['errors'], 1)
        self.assertEqual(groups[1]['score'], 100)

    def test_invalid_generated_panels_fail_before_adoption(self):
        with self.assertRaises(ValueError): normalize_panel({'questions': []})
        invalid = questions(); invalid['questions'][1]['intent'] = 'find'
        with self.assertRaises(ValueError): normalize_panel(invalid)
        invalid = questions(); invalid['questions'][1]['prompt'] = 'Here is sk-' + 'x' * 25
        with self.assertRaises(ValueError): normalize_panel(invalid)

    def test_public_https_endpoints_and_no_redirect_policy(self):
        for provider, url in [('deepseek', 'https://evil.example/v1'), ('custom', 'http://example.com'), ('custom', 'https://key@example.com/v1')]:
            with self.assertRaises(ValueError): validate_endpoint(provider, url)
        with patch('am_seo.question_lab.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('127.0.0.1', 443))]):
            with self.assertRaises(ValueError): validate_endpoint('custom', 'https://private.example')
        with self.assertRaises(ProviderError): NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.example')

    def test_provider_errors_do_not_expose_response_body_or_key(self):
        client = CompatibleClient({'base_url': 'https://api.deepseek.com/v1', 'model': 'fixture-model'}, self.key)
        with patch('am_seo.question_lab.build_opener') as opener:
            opener.return_value.open.side_effect = HTTPError('https://api.deepseek.com/v1/models', 401, self.key, {}, None)
            with self.assertRaises(ProviderError) as error: client.models()
        self.assertNotIn(self.key, str(error.exception))

    def test_interrupted_run_is_retained_as_error_after_restart(self):
        self.lab.data['job'] = {'status': 'testing', 'done': 2, 'id': 'fixture-interruption'}; self.lab.save()
        restored = QuestionLab(self.root, self.workspace, vault=self.vault)
        self.assertEqual(restored.state()['job']['status'], 'error')
        self.assertEqual(restored.state()['job']['done'], 2)


if __name__ == '__main__': unittest.main()
