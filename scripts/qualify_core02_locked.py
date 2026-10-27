#!/usr/bin/env python3
"""Read one frozen external corpus without importing its Python generators."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def checked_bytes(path, expected):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Missing or linked pinned file')
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected:
        raise ValueError('Pinned file hash mismatch: '+str(path))
    return raw

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vectors',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    lock=json.loads((ROOT/'config/wexp-vectors-core02.lock.json').read_bytes())
    if lock['repository']!='WEXP-dev/wexp-vectors' or not re.fullmatch('[0-9a-f]{40}',lock['commit']):
        raise ValueError('Exact external repository and commit required')
    repo=args.vectors.resolve()
    commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    if commit!=lock['commit']:
        raise ValueError('Vector checkout does not match pinned commit')
    if subprocess.check_output(['git','-C',str(repo),'status','--porcelain','--untracked-files=all'],text=True):
        raise ValueError('Vector checkout is not clean')
    if lock['corpus_path']!='vectors/WEXP-CORE-02-VECTORS-001':
        raise ValueError('Unexpected corpus path')
    corpus=repo/lock['corpus_path']
    if corpus.is_symlink() or not corpus.resolve().is_relative_to(repo):
        raise ValueError('Corpus escapes checkout')
    manifest=json.loads(checked_bytes(corpus/'manifest.json',lock['manifest_sha256']))
    if manifest['frozen_data']['path']!='corpus.json' or manifest['expanded_corpus_sha256']!=lock['expanded_corpus_sha256']:
        raise ValueError('Lock and corpus metadata disagree')
    raw=checked_bytes(corpus/'corpus.json',lock['expanded_corpus_sha256'])
    if len(raw)!=manifest['expanded_corpus_bytes']:
        raise ValueError('Corpus byte count mismatch')
    out=args.output_dir.resolve()
    if out.is_relative_to(repo):
        raise ValueError('Results must not modify the frozen external corpus checkout')
    out.mkdir(parents=True,exist_ok=False)
    reports=[]
    for optimized in (False,True):
        destination=out/('optimized.json' if optimized else 'normal.json')
        command=[sys.executable,'-B']+(['-O'] if optimized else [])+[
            '-m','wexp_ref.core02.qualify','--corpus',str(corpus/'corpus.json'),
            '--expected-sha256',lock['expanded_corpus_sha256'],'--output',str(destination)]
        subprocess.run(command,cwd=ROOT,check=True)
        reports.append(json.loads(destination.read_bytes()))
    if reports[0]['results']!=reports[1]['results']:
        raise ValueError('Normal and optimized logical results differ')
    summary={'status':'PASS_BOUNDED','vector_commit':commit,
             'manifest_sha256':lock['manifest_sha256'],'corpus_sha256':lock['expanded_corpus_sha256'],
             'cases_per_mode':reports[0]['case_count'],'full_conformance':False,
             'independent_interoperability':False,'coverage_profile_validation':False}
    (out/'SUMMARY.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,sort_keys=True))

if __name__=='__main__':
    try:
        main()
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as exc:
        print('Core-02 qualification failed: '+str(exc),file=sys.stderr)
        raise SystemExit(1)
