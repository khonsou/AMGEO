#!/usr/bin/env python3
"""Score real captured observations, separated by surface/platform/locale/mode.

Usage: python3 score_observations.py observations.jsonl metrics.json
No provider calls or fabricated baselines. Labels must be backed by an answer
and evidence captured by an agent. This calculator does not infer recommendation
or fact accuracy from a keyword match.
"""
import collections
import json
import pathlib
import sys
import urllib.parse

OFFICIAL_DOMAINS={'angrymiao.com','www.angrymiao.com','store.angrymiao.com','mall.angrymiao.com','m.angrymiao.com','cdn-www.angrymiao.com'}

def score(records):
    groups=collections.defaultdict(list)
    seen=set()
    for r in records:
        required=['run_id','query_id','surface','platform','locale','mode','status']
        if not all(r.get(k) for k in required):
            raise ValueError('Missing required observation fields')
        if r['status'] not in {'completed','no_ai_answer','error'}:
            raise ValueError('Unsupported observation status')
        if r['surface'] not in {'consumer','api_answer','search_retrieval'}:
            raise ValueError('Unsupported surface')
        identity=tuple(r[k] for k in required[:-1])
        if identity in seen:
            raise ValueError('Duplicate run/query observation')
        seen.add(identity)
        if r['status']=='completed' and r['surface']!='search_retrieval':
            for k in ['answer_text','brand_mentioned','suitable_recommendation','citations']:
                if k not in r: raise ValueError('Completed answer requires '+k)
            if not isinstance(r['brand_mentioned'],bool) or not isinstance(r['suitable_recommendation'],bool):
                raise ValueError('Agent classification labels must be explicit booleans')
            if not isinstance(r['citations'],list): raise ValueError('Citations must be a list')
            if not r.get('answer_text'): raise ValueError('Completed answer requires captured answer text')
        groups[tuple(r[k] for k in ['surface','platform','locale','mode'])].append(r)
    result=[]
    for key,rs in sorted(groups.items()):
        valid=[r for r in rs if r['status']!='error']
        entry=dict(zip(['surface','platform','locale','mode'],key))
        entry.update(attempted=len(rs),errors=len(rs)-len(valid),successful_tests=len(valid),no_ai_answers=sum(r['status']=='no_ai_answer' for r in valid))
        entry['failure_rate']=entry['errors']/len(rs)
        if key[0]=='search_retrieval':
            entry['scope']='retrieval_only_not_answer_citations'
            result.append(entry)
            continue
        def official(r):
            if r['status']!='completed': return False
            return any(urllib.parse.urlparse(url).hostname in OFFICIAL_DOMAINS for url in r['citations'])
        for name,predicate in [('brand_mention_rate',lambda r:r['status']=='completed' and r['brand_mentioned']),('official_citation_rate',official),('suitable_recommendation_rate',lambda r:r['status']=='completed' and r['suitable_recommendation'])]:
            entry[name]=sum(bool(predicate(r)) for r in valid)/len(valid) if valid else None
        answers=[r for r in valid if r['status']=='completed']
        entry['ai_answer_count']=len(answers)
        checks=[c for r in answers for c in r.get('fact_checks',[])]
        assessed=[c for c in checks if c.get('verdict') in {'supported','incorrect'}]
        entry['fact_assertions_assessed']=len(assessed)
        entry['fact_assertions_unresolved']=len(checks)-len(assessed)
        entry['fact_correctness_rate']=sum(c['verdict']=='supported' for c in assessed)/len(assessed) if assessed else None
        result.append(entry)
    return {'status':'measured' if records else 'not_run','observation_count':len(records),'groups':result,
            'note':'No AI answer counts as zero in end-to-end rates; network/errors excluded and reported. Empty evidence is not a zero-performance baseline. UI, API answers and retrieval-only runs are never merged. Labels and claim support require separate agent verification.'}

if __name__=='__main__':
    if len(sys.argv)!=3: raise SystemExit('Usage: score_observations.py observations.jsonl metrics.json')
    lines=pathlib.Path(sys.argv[1]).read_text(encoding='utf-8').splitlines()
    records=[json.loads(line) for line in lines if line.strip()]
    output=score(records)
    pathlib.Path(sys.argv[2]).write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':output['status'],'observation_count':len(records)},ensure_ascii=False))
