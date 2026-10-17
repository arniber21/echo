#!/usr/bin/env python3
"""Offline, auditable issue #13 evaluator for saved Echo Analysis JSON.

Inputs: a preparation manifest and a directory with <variant>.json Analysis files.
Optional annotations JSON: {"events":[{"id":"impact","source_second":132.0,
"tolerance_seconds":1.5}],"review":{"variant":{"unsupported_event_ids":[],
"missing_context_recognized":true}}}. Semantic judgments are HUMAN-reviewed.
Never infers collision, fault, or hallucination automatically from model wording.
"""
import argparse
import csv
import json
import math
from pathlib import Path


def source_time(segments, clip_time):
    if not isinstance(clip_time, (int, float)) or not math.isfinite(clip_time):
        return None
    for i, s in enumerate(segments):
        if s['clip_start'] - 1e-6 <= clip_time <= s['clip_end'] + 1e-6:
            if i < len(segments)-1 and clip_time >= s['clip_end'] - 1e-6:
                continue  # boundary belongs to next source segment
            return s['source_start'] + max(0, min(clip_time-s['clip_start'], s['source_end']-s['source_start']))
    return None


def evaluate(manifest, results, annotations):
    rows, details = [], {}
    expected = annotations.get('events', [])
    for name, variant in manifest['variants'].items():
        analysis = results.get(name)
        if analysis is None:
            rows.append({'variant':name,'status':'missing_result'})
            continue
        events = analysis.get('events', [])
        mapped = []
        invalid = []
        for event in events:
            start = event.get('source_start')
            end = event.get('source_end')
            a = source_time(variant['source_segments'], start)
            b = source_time(variant['source_segments'], end)
            if a is None or b is None:
                invalid.append(event.get('event_id', '<unknown>'))
            mapped.append({'id':event.get('event_id'), 'title':event.get('title'), 'evidence_type':event.get('evidence_type'), 'confidence':event.get('confidence'), 'clip_start':start, 'clip_end':end, 'original_start':a, 'original_end':b})
        covered = []
        for truth in expected:
            t = truth['source_second']
            if any(s['source_start'] <= t <= s['source_end'] for s in variant['source_segments']):
                covered.append(truth)
        matched, errors = [], []
        # Time proximity is a CANDIDATE only; it does not prove correct event semantics.
        for truth in covered:
            candidates = [(abs(e['original_start']-truth['source_second']),e['id']) for e in mapped if e['original_start'] is not None and abs(e['original_start']-truth['source_second']) <= truth.get('tolerance_seconds',1.5)]
            if candidates:
                error, event_id = min(candidates)
                matched.append({'annotation_id':truth['id'],'candidate_event_id':event_id,'timing_error_seconds':round(error,3),'semantic_match':'not_reviewed'})
                errors.append(error)
        review = annotations.get('review', {}).get(name, {})
        unsupported = review.get('unsupported_event_ids')
        row = {'variant':name,'status':'scored','events':len(events),'time_invalid_events':len(invalid),'annotated_events_visible':len(covered),'time_candidate_matches':len(matched),'mean_candidate_timing_error_seconds':round(sum(errors)/len(errors),3) if errors else '', 'unsupported_claims_human_reviewed':len(unsupported) if unsupported is not None else '', 'missing_context_recognized_human_reviewed':review.get('missing_context_recognized',''), 'analysis_mode':analysis.get('mode','unknown')}
        rows.append(row)
        details[name]={'mapped_events':mapped,'invalid_event_ids':invalid,'candidate_matches':matched,'human_review':review,'warning':'Timestamp candidates are NOT semantic accuracy or recall. Review original footage and model claims manually.'}
    return rows, details


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',type=Path,required=True)
    p.add_argument('--results-dir',type=Path,required=True)
    p.add_argument('--annotations',type=Path)
    p.add_argument('--output-dir',type=Path,default=Path('data/footage/issue13-eval/scores'))
    a=p.parse_args()
    manifest=json.loads(a.manifest.read_text())
    annotations=json.loads(a.annotations.read_text()) if a.annotations else {}
    results={}
    for name in manifest['variants']:
        f=a.results_dir/f'{name}.json'
        if f.is_file():
            data=json.loads(f.read_text())
            results[name]=data.get('analysis',data)
    rows, details=evaluate(manifest,results,annotations)
    a.output_dir.mkdir(parents=True,exist_ok=True)
    fields=['variant','status','events','time_invalid_events','annotated_events_visible','time_candidate_matches','mean_candidate_timing_error_seconds','unsupported_claims_human_reviewed','missing_context_recognized_human_reviewed','analysis_mode']
    with (a.output_dir/'comparison.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    (a.output_dir/'details.json').write_text(json.dumps(details,indent=2)+'\n')
    print(f"Saved {len(rows)} rows to {a.output_dir / 'comparison.csv'}; results available: {len(results)}")

if __name__=='__main__':main()
