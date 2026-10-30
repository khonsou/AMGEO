"""Test captured evidence and reversible patches without touching output QA files."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / 'outputs' / 'agent-kit'
REAL_PLACEHOLDER = 'Use this text to answer questions in as much detail as possible for your customers.'

def digest(value):
    return hashlib.sha256(value).hexdigest()


def load_validator():
    spec = importlib.util.spec_from_file_location('am_seo_test_validator', KIT / 'validate_batch.py')
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, 'dont_write_bytecode', True):
        spec.loader.exec_module(module)
    return module


def independently_replay(raw, operations):
    """Build ascending chunks, rather than mirror the validator's reverse slicing."""
    source = raw.decode('utf-8')
    chunks, transformed_spans = [], []
    source_cursor = 0
    output_length = 0
    for operation in sorted(operations, key=lambda op: op['target']['source_start_char_0_based']):
        target = operation['target']
        start, end = target['source_start_char_0_based'], target['source_end_char_exclusive']
        if not (source_cursor <= start < end <= len(source)):
            raise AssertionError('Operations overlap or point outside the original Unicode snapshot')
        original = source[start:end]
        if digest(original.encode('utf-8')) != target['old_value_sha256']:
            raise AssertionError('Original span hash mismatch')
        unchanged = source[source_cursor:start]
        chunks.extend([unchanged, operation['replacement']])
        transformed_start = output_length + len(unchanged)
        transformed_end = transformed_start + len(operation['replacement'])
        transformed_spans.append((transformed_start, transformed_end, original))
        output_length = transformed_end
        source_cursor = end
    chunks.append(source[source_cursor:])
    prepared = ''.join(chunks)
    restored_chunks, prepared_cursor = [], 0
    for start, end, original in transformed_spans:
        restored_chunks.extend([prepared[prepared_cursor:start], original])
        prepared_cursor = end
    restored_chunks.append(prepared[prepared_cursor:])
    return prepared.encode('utf-8'), ''.join(restored_chunks).encode('utf-8')


class ActualEvidenceReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.operations_document = json.loads((KIT / 'am-infinity-97.operations.json').read_text(encoding='utf-8'))
        cls.original_bytes = (KIT / cls.operations_document['source_snapshot_path']).read_bytes()

    def test_actual_thirteen_operations_are_pinned_to_exact_original_bytes(self):
        document = self.operations_document
        self.assertEqual(len(document['operations']), 13)
        self.assertEqual(len({op['id'] for op in document['operations']}), 13)
        original_hash = digest(self.original_bytes)
        self.assertEqual(original_hash, document['source_snapshot_sha256'])
        self.assertEqual(original_hash, document['precondition']['source_snapshot_sha256'])
        self.assertEqual(original_hash, document['rollback']['original_snapshot_sha256'])
        self.assertEqual(document['publication_status'], 'not_published')
        self.assertEqual(document['mode'], 'offline_patch_only')

    def test_actual_patch_and_full_inverse_restore_every_original_byte(self):
        prepared, restored = independently_replay(self.original_bytes, self.operations_document['operations'])
        self.assertEqual(digest(prepared), self.operations_document['prepared_html_sha256'])
        self.assertEqual(restored, self.original_bytes)
        self.assertNotEqual(prepared, self.original_bytes)
        text = prepared.decode('utf-8')
        self.assertNotIn(REAL_PLACEHOLDER, text)
        self.assertNotIn('Full Charge in 1.2s', text)
        self.assertNotIn('37g wired.', text)
        self.assertNotIn('Wired 39g (excl. battery), Wireless 47g', text)
        # Unrelated HTML survives the bounded patch, not only a claimed boolean.
        self.assertTrue(text.startswith(self.original_bytes.decode('utf-8')[:200]))
        self.assertEqual(text[-200:], self.original_bytes.decode('utf-8')[-200:])

    def test_a_one_character_source_change_cannot_replay_as_original(self):
        document = self.operations_document
        text = self.original_bytes.decode('utf-8')
        start = document['operations'][0]['target']['source_start_char_0_based']
        changed = (text[:start] + ('X' if text[start] != 'X' else 'Y') + text[start + 1:]).encode('utf-8')
        with self.assertRaisesRegex(AssertionError, 'hash mismatch'):
            independently_replay(changed, document['operations'])

    def test_conflicting_wired_weight_is_preserved_without_choosing_a_value(self):
        document = json.loads((KIT / 'product-facts.json').read_text(encoding='utf-8'))
        fact = next(item for item in document['facts'] if item['id'] == 'F-WIRED-WEIGHT')
        self.assertEqual(fact['status'], 'conflicting')
        self.assertIsNone(fact['fact']['value'])
        excerpts = ' '.join(item['exact_excerpt'] for item in fact['source'])
        self.assertIn('37g', excerpts)
        self.assertIn('39g', excerpts)


class IsolatedBatchValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = load_validator()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='am-seo-validator-')
        self.addCleanup(self.temporary.cleanup)
        self.fixture = Path(self.temporary.name) / 'kit'
        shutil.copytree(KIT, self.fixture, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))

    def invoke(self):
        # validate() writes qa-results.json; BASE is always a disposable copy.
        with mock.patch.object(self.validator, 'BASE', self.fixture), contextlib.redirect_stdout(io.StringIO()):
            code = self.validator.validate()
        return code, json.loads((self.fixture / 'qa-results.json').read_text(encoding='utf-8'))

    def rewrite_json(self, name, mutator):
        path = self.fixture / name
        document = json.loads(path.read_text(encoding='utf-8'))
        mutator(document)
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding='utf-8')
        return document

    def test_real_batch_passes_in_disposable_copy(self):
        code, report = self.invoke()
        self.assertEqual(code, 0)
        self.assertEqual(report['status'], 'passed')
        self.assertEqual(report['operations'], 13)
        self.assertEqual(report['live_storefront_writes'], 0)
        self.assertTrue(report['rollback_roundtrip'])
        self.assertTrue(all(check['passed'] for check in report['checks']))

    def test_modified_original_bytes_fail_the_source_hash_check(self):
        path = self.fixture / 'evidence' / 'am-infinity-97.source.html.txt'
        raw = path.read_bytes()
        path.write_bytes(b'!' + raw[1:])
        code, report = self.invoke()
        self.assertEqual(code, 1)
        self.assertTrue(any(c['check'] == 'source_sha256_matches' and not c['passed'] for c in report['checks']))

    def test_tampered_span_hash_is_detected(self):
        self.rewrite_json('am-infinity-97.operations.json',
                          lambda doc: doc['operations'][0]['target'].update(old_value_sha256='0' * 64))
        code, report = self.invoke()
        self.assertEqual(code, 1)
        self.assertTrue(any(c['check'].startswith('span:') and not c['passed'] for c in report['checks']))

    def test_untraceable_fact_reference_is_detected(self):
        self.rewrite_json('am-infinity-97.operations.json',
                          lambda doc: doc['operations'][0].update(evidence_ids=['MISSING-UNIT-FIXTURE-FACT']))
        code, report = self.invoke()
        self.assertEqual(code, 1)
        self.assertTrue(any(c['check'].startswith('provenance:') and not c['passed'] for c in report['checks']))

    def test_placeholder_reintroduction_fails_even_with_recomputed_output_hash(self):
        def reintroduce(doc):
            operation = next(item for item in doc['operations'] if item['id'] == 'O-HELP-01')
            operation['replacement'] = REAL_PLACEHOLDER
            raw = (self.fixture / doc['source_snapshot_path']).read_bytes()
            prepared, _ = independently_replay(raw, doc['operations'])
            doc['prepared_html_sha256'] = digest(prepared)
        self.rewrite_json('am-infinity-97.operations.json', reintroduce)
        code, report = self.invoke()
        self.assertEqual(code, 1, 'Validator must reject the actual source placeholder, even when patch hashes are internally consistent')
        self.assertTrue(any(c['check'] == 'target_placeholder_removed' and not c['passed'] for c in report['checks']))


if __name__ == '__main__':
    unittest.main()
