#!/usr/bin/env python3
"""Run Echo's real Gemini analysis on issue #13 variants, saving auditable JSON.

Run from the repository root with backend dependencies installed, for example:
  cd backend && uv run python ../scripts/run_eval_splices.py --manifest ../data/footage/issue13-eval/manifest.json

Never silently falls back to mock. Each variant is analyzed independently.
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, help='Default: <manifest directory>/results')
    p.add_argument('--cache-dir', type=Path, help='Default: <manifest directory>/cache')
    p.add_argument('--model', help='Override GEMINI_MODEL')
    p.add_argument('--fresh', action='store_true', help='Use isolated empty cache for new API requests')
    p.add_argument('--repeat', type=int, default=1, help='Independent repeats (requires --fresh if >1)')
    p.add_argument('--variants', nargs='+', help='Only run named variants')
    return p.parse_args()


async def run(args):
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / 'backend'))
    from dotenv import dotenv_values
    from rewind.analysis.pipeline import analyze
    from rewind.analysis.types import AnalysisSettings
    from rewind.models import Case, MediaFile, SourceType

    env = dotenv_values(root / 'backend' / '.env')
    api_key = os.environ.get('GEMINI_API_KEY') or env.get('GEMINI_API_KEY')
    if not api_key:
        raise RuntimeError('GEMINI_API_KEY missing: live evaluation requires an API key')
    model = args.model or os.environ.get('GEMINI_MODEL') or env.get('GEMINI_MODEL') or 'gemini-3.8-flash'
    manifest_path = args.manifest.expanduser().resolve(strict=True)
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('schema_version') != 1:
        raise ValueError('Unsupported manifest schema')
    variants = args.variants or list(manifest['variants'])
    if any(name not in manifest['variants'] for name in variants):
        raise ValueError('Unknown variant name')
    if args.repeat < 1 or (args.repeat > 1 and not args.fresh):
        raise ValueError('--repeat must be positive; use --fresh with --repeat > 1')
    out = (args.output_dir or manifest_path.parent / 'results').resolve()
    cache_root = (args.cache_dir or manifest_path.parent / 'cache').resolve()
    out.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)
    for name in variants:
        entry = manifest['variants'][name]
        filename = Path(entry['filename'])
        if filename.name != entry['filename']:
            raise ValueError('Manifest filenames must be simple basenames')
        path = manifest_path.parent / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        for iteration in range(1, args.repeat + 1):
            destination = out / (f'{name}.json' if args.repeat == 1 else f'{name}.run-{iteration}.json')
            if destination.exists():
                raise FileExistsError(f'Refusing to overwrite saved result: {destination}')
            from hashlib import sha256
            digest = sha256(path.read_bytes()).hexdigest()
            if digest != entry['sha256']:
                raise ValueError(f'Video hash mismatch: {name}')
            source_id = 'video-0'
            media = MediaFile(source_id=source_id, filename=filename.name,
                              source_type=SourceType.VIDEO, mime_type='video/mp4', url='',
                              sha256=digest, size_bytes=path.stat().st_size,
                              duration_seconds=entry['duration_seconds'])
            case = Case(case_id=f'issue13-{name}', title=f'Issue 13: {name}',
                        created_at=datetime.now(timezone.utc), media_files=[media])
            async def progress(stage, percent):
                print(f'[{name} #{iteration}] {percent}% {stage}', flush=True)
            # Fresh runs have distinct, persistent cache namespaces for auditability.
            cache = cache_root / (f'{name}-run-{iteration}' if args.fresh else 'shared')
            analysis = await analyze(case, {source_id: path}, progress,
                                     settings=AnalysisSettings(api_key=api_key, model=model,
                                                               mode='live', cache_dir=cache))
            if analysis.mode not in ('live', 'cached'):
                raise RuntimeError(f'Unexpected analysis mode: {analysis.mode}')
            payload = {'variant': name, 'iteration': iteration, 'model': model,
                       'generated_at': datetime.now(timezone.utc).isoformat(),
                       'video_sha256': digest, 'manifest_schema_version': 1,
                       'analysis': analysis.model_dump(mode='json')}
            destination.write_text(json.dumps(payload, indent=2) + '\n')
            print(f'Saved {destination} ({analysis.mode}, {len(analysis.events)} events)')


def main():
    args = parse_args()
    try:
        asyncio.run(run(args))
    except Exception as error:
        # Provider exceptions may contain secrets or request bodies; do not echo them.
        print(f'Evaluation stopped: {type(error).__name__}. Check inputs, credentials and provider availability.', file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
