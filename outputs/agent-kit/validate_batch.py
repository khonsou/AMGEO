#!/usr/bin/env python3
"""Validate actual prepared artifacts; no LLM, network or storefront writes."""
import collections
import datetime
import hashlib
import json
import pathlib
import re
import sys

BASE = pathlib.Path(__file__).resolve().parent

def load(name):
    return json.loads((BASE / name).read_text(encoding='utf-8'))

def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def validate():
    checks = []
    def check(name, condition, detail=''):
        checks.append({'check': name, 'passed': bool(condition), 'detail': detail})

    facts = load('product-facts.json')
    ops = load('am-infinity-97.operations.json')
    raw_bytes = (BASE / 'evidence/am-infinity-97.source.html.txt').read_bytes()
    source = raw_bytes.decode('utf-8')  # Preserve CRLF: offsets use original Unicode text.
    check('source_sha256_matches', digest(source) == ops['source_snapshot_sha256'])
    check('prepared_only', ops['publication_status'] == 'not_published' and ops['mode'] == 'offline_patch_only')
    fact_ids = {f['id'] for f in facts['facts']}
    check('unique_fact_ids', len(fact_ids) == len(facts['facts']))
    for fact in facts['facts']:
        for index, evidence in enumerate(fact['source']):
            start = evidence['start_char_0_based']
            end = evidence['end_char_exclusive']
            excerpt = source[start:end]
            check(f"fact_source:{fact['id']}:{index}", excerpt == evidence['exact_excerpt'] and digest(excerpt) == evidence['excerpt_sha256'])

    operations = sorted(ops['operations'], key=lambda x:x['target']['source_start_char_0_based'])
    previous_end = -1
    for op in operations:
        target = op['target']
        start,end = target['source_start_char_0_based'],target['source_end_char_exclusive']
        check(f"span:{op['id']}", 0 <= start < end <= len(source) and start >= previous_end and digest(source[start:end]) == target['old_value_sha256'])
        check(f"provenance:{op['id']}", all(i in fact_ids for i in op['evidence_ids']))
        previous_end = end
    prepared = source
    for op in reversed(operations):
        target = op['target']
        prepared = prepared[:target['source_start_char_0_based']] + op['replacement'] + prepared[target['source_end_char_exclusive']:]
    check('prepared_sha256_matches', digest(prepared) == ops['prepared_html_sha256'])
    # Inverse replacements use transformed offsets and restore original spans.
    delta = 0
    inverse = []
    for op in operations:
        target = op['target']
        start,end = target['source_start_char_0_based'],target['source_end_char_exclusive']
        transformed_start = start + delta
        inverse.append((transformed_start,transformed_start+len(op['replacement']),source[start:end]))
        delta += len(op['replacement'])-(end-start)
    restored = prepared
    for start,end,old in reversed(inverse):
        restored = restored[:start]+old+restored[end:]
    check('rollback_exact_roundtrip', restored.encode('utf-8') == raw_bytes)
    placeholders = (
        'Use this text to share information about your brand with your customers.',
        'Use this text to answer questions in as much detail as possible for your customers.',
    )
    check('target_placeholder_removed', not any(value in prepared for value in placeholders))
    # Validate the narrow intended drafts, not every value in the captured whole site.
    for name in ['battery-mechanism.en.md','battery-mechanism.zh-CN.md']:
        draft = (BASE/name).read_text(encoding='utf-8')
        check('no_unresolved_numeric_claim:'+name, re.search(r'\b(?:37|39|47)\s*g\b|\b1\.2\b|\b165\b',draft,re.I) is None)
        check('source_link_present:'+name, facts['source_url'] in draft)
    seed = load('query-seeds.json')['queries']
    check('question_ids_unique',len({q['id'] for q in seed})==48==len(seed))
    for language in ['en-US','zh-CN']:
        group=[q for q in seed if q['language']==language]
        check('questions_per_language:'+language,len(group)==24 and sum(q['branded'] for q in group)==6)
        check('question_category_counts:'+language,dict(collections.Counter(q['id'].split('-')[1] for q in group))=={'M':12,'K':8,'S':4})
    task_data=load('tasks.json')
    task_ids={t['id'] for t in task_data['tasks']}
    check('task_ids_unique',len(task_ids)==len(task_data['tasks']))
    for task in task_data['tasks']:
        check('task_contract:'+task['id'],bool(task['agent'] and task['acceptance'] and task['outputs']) and all(d in task_ids for d in task['depends_on']))
        if task['status']=='completed':
            check('completed_artifacts_exist:'+task['id'],all((BASE/name).exists() for name in task['outputs']))
    report={'validated_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'status':'passed' if all(c['passed'] for c in checks) else 'failed',
      'checks_total':len(checks),'checks':checks,'fact_records':len(facts['facts']),
      'operations':len(operations),'question_count':len(seed),
      'full_snapshot_replay':True,'rollback_roundtrip':digest(restored)==digest(source),
      'live_storefront_writes':0,'live_eval_runs':0,
      'scope':'Offline artifact integrity, exact source spans, patch replay/rollback and structural contracts. Does not certify product measurements, live SEO, rich results eligibility, factual truth beyond captured source claims, or CMS deployment.'}
    (BASE/'qa-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['status','checks_total','fact_records','operations','question_count','rollback_roundtrip','live_storefront_writes']},ensure_ascii=False))
    return 0 if report['status']=='passed' else 1

if __name__=='__main__':
    sys.exit(validate())
