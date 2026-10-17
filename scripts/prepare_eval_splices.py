#!/usr/bin/env python3
"""Create deterministic, source-clock-aware video variants for Echo issue #13.

Requires ffmpeg/ffprobe. Source videos are never modified. Human annotation is
required separately; these temporal cuts do not assert an impact timestamp.
"""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def duration(path):
    p = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(path)],check=True,capture_output=True,text=True)
    return float(json.loads(p.stdout)['format']['duration'])


def encode(source, destination, segments):
    # Encode segments independently, then concat them; source time maps remain explicit.
    chunks = []
    for i, (start, end) in enumerate(segments):
        part = destination.parent / f'.{destination.stem}-{i}.mp4'
        subprocess.run(['ffmpeg','-y','-v','error','-ss',str(start),'-i',str(source),'-t',str(end-start),'-map','0:v:0','-map','0:a:0?','-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(part)],check=True)
        chunks.append(part)
    if len(chunks) == 1:
        chunks[0].replace(destination)
    else:
        listing = destination.parent / f'.{destination.stem}-concat.txt'
        try:
            listing.write_text(''.join("file '" + p.name + "'\n" for p in chunks))
            subprocess.run(['ffmpeg','-y','-v','error','-f','concat','-safe','0','-i',str(listing),'-c','copy',str(destination)],check=True)
        finally:
            listing.unlink(missing_ok=True)
            for p in chunks: p.unlink(missing_ok=True)


def plan(start, length, impact):
    end = start + length
    if not start < impact < end:
        raise ValueError('impact timestamp must fall strictly inside the selected incident')
    # Use a fixed 2-second exclusion window around the annotated event.
    pad = min(1.0, (impact-start)/3, (end-impact)/3)
    left, right = impact-pad, impact+pad
    return {
        'full': [(start,end)],
        'pre_impact': [(start,left)],
        'impact_only': [(left,right)],
        'post_impact': [(right,end)],
        'short_context': [(max(start,impact-3),min(end,impact+3))],
        'omitted_interval': [(start,left),(right,end)],
        'noncontiguous': [(start,min(start+2,left)),(right,end)],
    }


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('source',type=Path)
    ap.add_argument('--start',type=float,required=True)
    ap.add_argument('--duration',type=float,required=True)
    ap.add_argument('--impact',type=float,required=True,help='Human-reviewed impact timestamp in ORIGINAL source seconds')
    ap.add_argument('--output-dir',type=Path,default=Path('data/footage/issue13-eval'))
    args=ap.parse_args()
    source=args.source.expanduser().resolve(strict=True)
    if not all(map(math.isfinite,[args.start,args.duration,args.impact])) or args.start<0 or args.duration<=0:
        ap.error('Invalid time arguments')
    if args.start+args.duration>duration(source)+0.01:
        ap.error('Selected interval exceeds source duration')
    variants=plan(args.start,args.duration,args.impact)
    out=args.output_dir.resolve()
    if out==source.parent or source==out or out in source.parents:
        ap.error('Output directory must not contain the original recording')
    out.mkdir(parents=True,exist_ok=True)
    manifest={'schema_version':1,'source':{'filename':source.name,'sha256':sha256(source),'duration_seconds':duration(source)},'impact_annotation':{'source_second':args.impact,'status':'human_review_required'},'variants':{}}
    for name,segments in variants.items():
        target=out/f'{name}.mp4'
        if target==source: ap.error('Refusing to overwrite original')
        encode(source,target,segments)
        offset=0.0
        mapping=[]
        for a,b in segments:
            mapping.append({'clip_start':offset,'clip_end':offset+(b-a),'source_start':a,'source_end':b})
            offset+=b-a
        manifest['variants'][name]={'filename':target.name,'sha256':sha256(target),'duration_seconds':duration(target),'source_segments':mapping,'independent_evidence':False}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Created {len(variants)} variants and {out / "manifest.json"}')

if __name__=='__main__':main()
