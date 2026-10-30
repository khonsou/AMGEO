"""Measurement-contract tests. All observations here are synthetic unit fixtures."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCORER = ROOT / 'outputs' / 'agent-kit' / 'score_observations.py'

def load_scorer():
    spec = importlib.util.spec_from_file_location('am_seo_test_scorer', SCORER)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, 'dont_write_bytecode', True):
        spec.loader.exec_module(module)
    return module


def observation(query_id='fixture-question', **overrides):
    record = {
        'run_id': 'unit-fixture-run', 'query_id': query_id,
        'surface': 'consumer', 'platform': 'unit-fixture-platform',
        'locale': 'en-US', 'mode': 'web-search', 'status': 'completed',
        'answer_text': 'Synthetic fixture answer; not a measured model response.',
        'brand_mentioned': True, 'suitable_recommendation': True,
        'citations': ['https://store.angrymiao.com/products/fixture'],
    }
    record.update(overrides)
    return record


class ObservationScoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scorer = load_scorer()

    def test_no_ai_answer_is_zero_and_network_error_is_excluded(self):
        records = [
            observation('yes', fact_checks=[{'verdict': 'supported'}, {'verdict': 'incorrect'}, {'verdict': 'unresolved'}]),
            observation('no', brand_mentioned=False, suitable_recommendation=False, citations=[], fact_checks=[{'verdict': 'supported'}]),
            observation('absent', status='no_ai_answer'),
            observation('network', status='error'),
        ]
        group = self.scorer.score(records)['groups'][0]
        self.assertEqual((group['attempted'], group['errors'], group['successful_tests']), (4, 1, 3))
        self.assertEqual((group['ai_answer_count'], group['no_ai_answers']), (2, 1))
        for key in ('brand_mention_rate', 'official_citation_rate', 'suitable_recommendation_rate'):
            self.assertAlmostEqual(group[key], 1 / 3, msg=key)
        self.assertEqual(group['failure_rate'], 1 / 4)
        self.assertEqual((group['fact_assertions_assessed'], group['fact_assertions_unresolved']), (3, 1))
        self.assertAlmostEqual(group['fact_correctness_rate'], 2 / 3)

    def test_only_errors_do_not_create_a_zero_performance_baseline(self):
        group = self.scorer.score([observation(status='error')])['groups'][0]
        self.assertEqual(group['successful_tests'], 0)
        self.assertEqual(group['failure_rate'], 1)
        for key in ('brand_mention_rate', 'official_citation_rate', 'suitable_recommendation_rate', 'fact_correctness_rate'):
            self.assertIsNone(group[key], key)

    def test_no_ai_answer_needs_no_captured_answer_or_labels(self):
        minimal = {key: value for key, value in observation(status='no_ai_answer').items()
                   if key not in {'answer_text', 'brand_mentioned', 'suitable_recommendation', 'citations'}}
        group = self.scorer.score([minimal])['groups'][0]
        self.assertEqual(group['successful_tests'], 1)
        self.assertEqual(group['brand_mention_rate'], 0)
        self.assertEqual(group['official_citation_rate'], 0)

    def test_official_citations_use_exact_hostname_not_substrings(self):
        official = [
            'https://angrymiao.com/fixture', 'https://www.angrymiao.com/en/',
            'https://store.angrymiao.com:443/fixture', 'https://mall.angrymiao.com/products/fixture',
            'https://m.angrymiao.com/products/fixture', 'https://cdn-www.angrymiao.com/fixture.pdf',
            'https://STORE.ANGRYMIAO.COM/fixture',
        ]
        lookalikes = [
            'https://angrymiao.com.evil.example/fixture',
            'https://store.angrymiao.com.evil.example/fixture',
            'https://angrymiao.com@evil.example/fixture',
            'https://angrymiao-com.example/fixture',
            'https://notangrymiao.com/fixture',
            'https://evil.example/angrymiao.com',
            'https://evil.example/?next=https://store.angrymiao.com',
            'https://evil.example/#angrymiao.com',
        ]
        for citation in official + lookalikes:
            with self.subTest(citation=citation):
                group = self.scorer.score([observation(citations=[citation])])['groups'][0]
                self.assertEqual(group['official_citation_rate'], 1 if citation in official else 0)

    def test_surfaces_locales_platforms_and_modes_never_merge(self):
        records = [
            observation('consumer'), observation('api', surface='api_answer'),
            observation('retrieval', surface='search_retrieval'),
            observation('chinese', locale='zh-CN'), observation('mode', mode='no-search'),
            observation('platform', platform='another-unit-fixture-platform'),
        ]
        result = self.scorer.score(records)
        self.assertEqual(len(result['groups']), 6)
        keys = {(g['surface'], g['platform'], g['locale'], g['mode']) for g in result['groups']}
        self.assertEqual(len(keys), 6)
        self.assertTrue(all(g['attempted'] == 1 for g in result['groups']))
        retrieval = next(g for g in result['groups'] if g['surface'] == 'search_retrieval')
        self.assertEqual(retrieval['scope'], 'retrieval_only_not_answer_citations')
        for key in ('brand_mention_rate', 'official_citation_rate', 'suitable_recommendation_rate', 'ai_answer_count'):
            self.assertNotIn(key, retrieval)

    def test_duplicate_run_query_rejected_even_when_status_changes(self):
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.scorer.score([observation(), observation(status='error')])

    def test_same_question_from_distinct_runs_is_allowed(self):
        result = self.scorer.score([observation(), observation(run_id='second-unit-fixture-run')])
        self.assertEqual(result['observation_count'], 2)
        self.assertEqual(result['groups'][0]['attempted'], 2)

    def test_empty_samples_are_not_run_with_no_groups(self):
        result = self.scorer.score([])
        self.assertEqual(result['status'], 'not_run')
        self.assertEqual(result['observation_count'], 0)
        self.assertEqual(result['groups'], [])

    def test_completed_answers_require_explicit_labels_and_text(self):
        for overrides in ({'brand_mentioned': 'yes'}, {'suitable_recommendation': 1},
                          {'answer_text': ''}, {'citations': 'https://angrymiao.com'}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.scorer.score([observation(**overrides)])

    def test_unknown_status_surface_or_missing_identity_rejected(self):
        for overrides in ({'status': 'synthetic_success'}, {'surface': 'mixed'}, {'run_id': ''}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                self.scorer.score([observation(**overrides)])

    def test_scorer_cli_empty_fixture_writes_only_temporary_result(self):
        with tempfile.TemporaryDirectory(prefix='am-seo-scorer-') as temporary:
            input_path = Path(temporary) / 'observations.jsonl'
            output_path = Path(temporary) / 'metrics.json'
            input_path.write_text('', encoding='utf-8')
            completed = subprocess.run([sys.executable, str(SCORER), str(input_path), str(output_path)],
                                       cwd=temporary, text=True, capture_output=True, timeout=15,
                                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(output_path.read_text(encoding='utf-8'))
            self.assertEqual(result['status'], 'not_run')
            self.assertEqual(result['groups'], [])


if __name__ == '__main__':
    unittest.main()
