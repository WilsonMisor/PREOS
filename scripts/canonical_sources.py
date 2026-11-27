#!/usr/bin/env python3
"""Portable, byte-exact four-source preservation, independent of the workspace."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'source-package/four-sources'
# Immutable input-version invariants, not runtime catalogue counts.
SOURCES={
    'source-1':('five_dimension_software_risk_master_catalogue_40_field_edition_updated_with_app_legal_platform_risks.md','cfb5a9e7323ffcd9e27b5d0da73b8d896c989550b27fd6ba38678a17d1ab6a4b'),
    'source-2':('AI_Assisted_and_Vibe_Coded_Software_Production_Readiness_Framework.docx','cb97fb8240db22a05566dc72b67e7d8eb02b6106df0f5d9719d9b833330b5009'),
    'source-3':('production-risk-economics-and-evolution-operating-system-for-vibe-coding.md','f4bbbd8c98f7e2a7fd7144979c8765562158abbd8e680fef3940a651c070d36e'),
    'source-4':('production_risk_economics_evolution_master_prompt.txt','94608e09d6f3a80cef6961a3cf3a97cb63a66a009930b212caec0794248eed34'),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def preserve(input_dir, destination=DIRECTORY):
    records=[]
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=True)
    for sid,(name,expected) in SOURCES.items():
        raw=(Path(input_dir)/name).read_bytes()
        if digest(raw)!=expected:
            raise ValueError('source bytes differ from governing inputs: '+sid)
        compressed=gzip.compress(raw,mtime=0)
        path=destination/(sid+'.gz')
        path.write_bytes(compressed)
        records.append({'source_id':sid,'original_name':name,'sha256':expected,'bytes':len(raw),
                        'preserved_path':path.name,'encoding':'gzip','preserved_sha256':digest(compressed)})
    manifest={'schema_version':'four-source-preservation-v1','source_count':len(records),'sources':records}
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    return manifest


def source_bytes(source_id,directory=DIRECTORY):
    if source_id not in SOURCES:
        raise ValueError('unknown canonical source identity')
    manifest=json.loads((Path(directory)/'manifest.json').read_text(encoding='utf-8'))
    records={r['source_id']:r for r in manifest['sources']}
    if len(records)!=len(manifest['sources']) or set(records)!=set(SOURCES):
        raise ValueError('source manifest identities do not match governing inputs')
    record=records[source_id]
    if record['sha256']!=SOURCES[source_id][1] or record['original_name']!=SOURCES[source_id][0]:
        raise ValueError('source manifest authority mismatch')
    path=(Path(directory)/record['preserved_path']).resolve()
    if not path.is_relative_to(Path(directory).resolve()):
        raise ValueError('source archive path escapes preservation directory')
    compressed=path.read_bytes()
    if digest(compressed)!=record['preserved_sha256']:
        raise ValueError('source archive changed')
    raw=gzip.decompress(compressed)
    if digest(raw)!=record['sha256'] or len(raw)!=record['bytes']:
        raise ValueError('preserved source is not byte-exact')
    return raw


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preserve-from',type=Path)
    args=parser.parse_args()
    if args.preserve_from:
        preserve(args.preserve_from)
    result={sid:{'sha256':digest(source_bytes(sid)),'bytes':len(source_bytes(sid))} for sid in SOURCES}
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
