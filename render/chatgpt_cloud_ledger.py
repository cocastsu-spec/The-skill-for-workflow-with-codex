#!/usr/bin/env python3
"""No-API ChatGPT-cloud file/ledger helper. It DOES NOT visually analyze images.
The ChatGPT assistant must actually view an image before writing each observation.
Designed for ChatGPT Data Analysis hosted Python and transferable to hosted sites.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path
from datetime import datetime, timezone

MAX_FILES = 10000
ALLOWED_IMAGES = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}

def supported_image_entries(zf):
    return [e for e in zf.infolist() if not e.is_dir() and Path(e.filename).suffix.lower() in ALLOWED_IMAGES]

MAX_TOTAL_BYTES = 4 * 1024 ** 3
MAX_SINGLE_BYTES = 30 * 1024 ** 2


def write_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def image_valid(path: Path, suffix: str):
    with path.open('rb') as f:
        header = f.read(16)
    good = (suffix == '.png' and header.startswith(b'\x89PNG\r\n\x1a\n')) or (suffix in ('.jpg','.jpeg') and header.startswith(b'\xff\xd8\xff')) or (suffix == '.webp' and header.startswith(b'RIFF') and header[8:12] == b'WEBP')
    if not good:
        raise ValueError(f'Invalid {suffix} image signature: {path.name}')



def state(root):
    path = root / 'manifest.json'
    if not path.is_file():
        raise ValueError('No manifest; run ingest first')
    return read_json(path)


def ingest(args):
    root, path = args.workspace, args.zip
    if (root / 'manifest.json').exists():
        raise ValueError('Workspace already initialized; refuse destructive overwrite')
    root.mkdir(parents=True, exist_ok=True)
    entries, total, existing = [], 0, set()
    with zipfile.ZipFile(path) as zf:
        zips = supported_image_entries(zf)
        if not zips or len(zips) > MAX_FILES:
            raise ValueError(f'Image count invalid: {len(zips)} (supports PNG/JPG/JPEG/WebP)')
        for i, info in enumerate(zips, 1):
            if info.file_size > MAX_SINGLE_BYTES:
                raise ValueError(f'Individual image exceeds safe size: {info.filename}')
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                raise ValueError('Uncompressed ZIP is too large')
            original_name = info.filename.replace('\\', '/')
            if original_name in existing:
                raise ValueError(f'Duplicate ZIP path: {original_name}')
            existing.add(original_name)
            if original_name.startswith('/') or '..' in Path(original_name).parts:
                raise ValueError(f'Unsafe ZIP path: {original_name}')
            iid = f'IMG-{i:06d}'
            suffix = Path(original_name).suffix.lower()
            target = root / 'originals' / f'{iid}{suffix}'
            target.parent.mkdir(parents=True, exist_ok=True)
            h = hashlib.sha256()
            actual = 0
            with zf.open(info, 'r') as src, target.open('wb') as dst:
                while True:
                    chunk = src.read(1048576)
                    if not chunk:
                        break
                    actual += len(chunk)
                    if actual > MAX_SINGLE_BYTES:
                        raise ValueError('Decompression size exceeded')
                    h.update(chunk)
                    dst.write(chunk)
            image_valid(target, suffix)
            entries.append({'image_id': iid, 'source_path': original_name,
                            'sha256': h.hexdigest(), 'bytes': actual,
                            'original': str(target.relative_to(root)), 'mime_type': ALLOWED_IMAGES[suffix]})
    write_json(root / 'manifest.json', {'created_utc': datetime.now(timezone.utc).isoformat(),
                'count': len(entries), 'images': entries})
    print(json.dumps({'ingested': len(entries), 'workspace': str(root)}, ensure_ascii=False))


def record_dir(root, stage):
    return root / 'observations' / stage


def saved_records(root, stage):
    return {p.stem for p in record_dir(root, stage).glob('IMG-*.json')}


def next_image(args):
    manifest = state(args.workspace)
    allowed = [e['image_id'] for e in manifest['images']]
    if args.stage == 'deep':
        sels = read_json(args.workspace / 'selections.json')
        allowed = [iid for ids in sels.values() for iid in ids]
    done = saved_records(args.workspace, args.stage)
    found = [e for e in manifest['images'] if e['image_id'] in allowed and e['image_id'] not in done]
    if args.image_id:
        found = [e for e in manifest['images'] if e['image_id'] == args.image_id and e['image_id'] in allowed]
    if not found:
        print(json.dumps({'status': 'complete', 'stage': args.stage, 'remaining': 0}))
        return
    e = found[0]
    path = args.workspace / e['original']
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != e['sha256']:
        raise ValueError(f'Image bytes changed: {e["image_id"]}')
    print(json.dumps({'status': 'pending', 'stage': args.stage,
                      'image_id': e['image_id'], 'source_path': e['source_path'],
                      'sha256': e['sha256'], 'image_path': str(path), 'mime_type':e.get('mime_type','image/png'),
                      'remaining': len(found)}, ensure_ascii=False))


def record(args):
    root, manifest = args.workspace, state(args.workspace)
    image_map = {e['image_id']: e for e in manifest['images']}
    if args.image_id not in image_map:
        raise ValueError('Unknown image ID')
    if args.stage == 'deep':
        selected = read_json(root / 'selections.json')
        if args.image_id not in {i for v in selected.values() for i in v}:
            raise ValueError('Image was not selected for deep analysis')
        if args.image_id not in saved_records(root, 'first'):
            raise ValueError('Deep record requires first-pass record')
    p = record_dir(root, args.stage) / f'{args.image_id}.json'
    if p.exists():
        raise ValueError('Existing observation; no silent overwrite')
    entry = image_map[args.image_id]
    src = root / entry['original']
    if hashlib.sha256(src.read_bytes()).hexdigest() != entry['sha256']:
        raise ValueError('Image content changed')
    payload = read_json(args.json)
    if not isinstance(payload, dict):
        raise ValueError('Analysis payload must be a JSON object')
    if payload.get('image_id') != args.image_id or payload.get('sha256') != entry['sha256']:
        raise ValueError('Analysis must contain matching image_id and original sha256')
    if payload.get('observed_with') != 'chatgpt_visual':
        raise ValueError('observed_with must be chatgpt_visual; do not use this if image not actually shown to GPT')
    if len(str(payload.get('visible_evidence', '')).strip()) < 24:
        raise ValueError('Require visual evidence (text/character/layout/scene), not an empty receipt')
    payload['_ledger'] = {'stage': args.stage, 'saved_utc': datetime.now(timezone.utc).isoformat(),
                          'verification_level': 'self_attested_visual_inspection_not_api_verified'}
    write_json(p, payload)
    print(json.dumps({'saved': str(p)}, ensure_ascii=False))


def set_groups(args):
    root, manifest = args.workspace, state(args.workspace)
    source = read_json(args.json)
    groups = source.get('groups') if isinstance(source, dict) else None
    if not isinstance(groups, dict) or not groups:
        raise ValueError('Expected {"groups": {"group": ["IMG-..."]}}')
    flat = [i for ids in groups.values() for i in ids]
    ids = {e['image_id'] for e in manifest['images']}
    if not all(isinstance(v, list) and len(v) >= 5 for v in groups.values()):
        raise ValueError('Each group needs >=5 available original images')
    if len(flat) != len(set(flat)) or set(flat) != ids:
        raise ValueError('Groups must assign every source image exactly once')
    if len(saved_records(root, 'first')) != len(ids):
        raise ValueError('Full first-pass coverage required before taxonomy')
    write_json(root / 'groups.json', groups)
    print(json.dumps({'groups': len(groups), 'assigned': len(flat)}))


def set_selection(args):
    root = args.workspace
    groups = read_json(root / 'groups.json')
    selected = read_json(args.json)
    if set(selected) != set(groups):
        raise ValueError('Exactly one selection for each group required')
    for group, ids in selected.items():
        if not isinstance(ids, list) or len(ids) != 5 or len(set(ids)) != 5:
            raise ValueError(f'{group}: select exactly five distinct original PNGs')
        if not set(ids).issubset(set(groups[group])):
            raise ValueError(f'{group}: cannot select image outside its category')
    write_json(root / 'selections.json', selected)
    print(json.dumps({'selected_images': sum(map(len, selected.values()))}))


def audit(root):
    manifest = state(root)
    n = len(manifest['images'])
    a = saved_records(root, 'first')
    b = saved_records(root, 'deep')
    result = {'source_png_count': n, 'first_pass_count': len(a), 'deep_count': len(b),
              'first_missing': [e['image_id'] for e in manifest['images'] if e['image_id'] not in a],
              'verification_level': 'file_coverage_only; visual_inspection_self_attested'}
    if (root / 'groups.json').exists():
        groups = read_json(root / 'groups.json')
        result['group_count'] = len(groups)
    if (root / 'selections.json').exists():
        selection = read_json(root / 'selections.json')
        expected = {i for xs in selection.values() for i in xs}
        result['deep_expected'] = len(expected)
        result['deep_missing'] = sorted(expected - b)
    # Counts alone are insufficient: verify every receipt matches the expected image.
    invalid = []
    for stage, ids_in_stage in [('first', a), ('deep', b)]:
        for iid in ids_in_stage:
            e = next((e for e in manifest['images'] if e['image_id'] == iid), None)
            try:
                rec = read_json(record_dir(root, stage) / (iid + '.json'))
                if e is None or not isinstance(rec, dict) or rec.get('image_id') != iid or rec.get('sha256') != e['sha256'] or rec.get('observed_with') != 'chatgpt_visual':
                    invalid.append(stage + ':' + iid)
            except (ValueError, OSError, KeyError, TypeError):
                invalid.append(stage + ':' + iid)
    result['invalid_records'] = sorted(invalid)
    result['file_gate_pass'] = (len(a) == n and not invalid and
        result.get('deep_expected', -1) == len(b) and not result.get('deep_missing', []) and
        (root/'style_dna.json').is_file())
    return result


def package(args):
    root = args.workspace
    check = audit(root)
    if not check['file_gate_pass']:
        raise ValueError(f'Incomplete file gate: {check}')
    manifest = state(root)
    groups = read_json(root / 'groups.json')
    selection = read_json(root / 'selections.json')
    inverse = {e['image_id']:e for e in manifest['images']}
    # Revalidate images and all source records before exporting.
    for e in manifest['images']:
        if hashlib.sha256((root/e['original']).read_bytes()).hexdigest() != e['sha256']:
            raise ValueError('SHA mismatch: '+e['image_id'])
    allfirst = [read_json(record_dir(root, 'first') / (e['image_id']+'.json')) for e in manifest['images']]
    alldeep = [read_json(record_dir(root, 'deep') / (iid+'.json')) for ids in selection.values() for iid in ids]
    write_json(root / 'audit.json', check)
    write_json(root / 'thumbnail_analysis.json', {'manifest':manifest, 'groups':groups,
              'selected':selection, 'first_pass_by_image':allfirst,
              'deep_analysis_by_image':alldeep, 'style_dna':read_json(root/'style_dna.json'),
              'audit':check})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for name in ('manifest.json','groups.json','selections.json','audit.json','thumbnail_analysis.json','style_dna.json'):
            zf.write(root/name, name)
        for kind in ('first','deep'):
            for rec in (root/'observations'/kind).glob('*.json'):
                zf.write(rec, f'reports/{kind}/{rec.name}')
        for group, ids in selection.items():
            # Include a digest: distinct groups must never merge after filename sanitization.
            base = ''.join(x if x.isascii() and (x.isalnum() or x in '-_') else '_' for x in group).strip('_')[:52] or 'group'
            clean = base + '__' + hashlib.sha256(group.encode('utf-8')).hexdigest()[:12]
            for rank, iid in enumerate(ids, 1):
                zf.write(root/inverse[iid]['original'], f'groups/{clean}/{rank:02d}_{iid}{Path(inverse[iid]["original"]).suffix}')
    print(json.dumps({'output':str(args.output),'audit':check},ensure_ascii=False))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace',required=True,type=Path)
    sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('ingest');q.add_argument('--zip',required=True,type=Path)
    q=sub.add_parser('next');q.add_argument('--stage',choices=['first','deep'],required=True);q.add_argument('--image-id')
    q=sub.add_parser('record');q.add_argument('--stage',choices=['first','deep'],required=True);q.add_argument('--image-id',required=True);q.add_argument('--json',required=True,type=Path)
    q=sub.add_parser('groups');q.add_argument('--json',required=True,type=Path)
    q=sub.add_parser('select');q.add_argument('--json',required=True,type=Path)
    q=sub.add_parser('style');q.add_argument('--json',required=True,type=Path)
    sub.add_parser('audit')
    q=sub.add_parser('package');q.add_argument('--output',required=True,type=Path)
    args=p.parse_args()
    if args.command=='ingest':ingest(args)
    elif args.command=='next':next_image(args)
    elif args.command=='record':record(args)
    elif args.command=='groups':set_groups(args)
    elif args.command=='select':set_selection(args)
    elif args.command=='style':
        state(args.workspace)
        if not (args.workspace/'selections.json').exists():raise ValueError('Select images first')
        style=read_json(args.json)
        if not isinstance(style,dict) or not style:raise ValueError('Empty style synthesis')
        write_json(args.workspace/'style_dna.json',style)
    elif args.command=='audit':print(json.dumps(audit(args.workspace),ensure_ascii=False,indent=2))
    elif args.command=='package':package(args)

if __name__=='__main__':
    main()
