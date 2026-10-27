#!/usr/bin/env python3
"""Verify the externally pinned Core-02 checkout before executing its code."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--lock', type=Path, default=Path('config/wexp-vectors-core02.lock.json'))
    args = parser.parse_args()
    lock = json.loads(args.lock.read_text(encoding='utf-8'))
    root = args.repository.resolve()
    result = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'],
                            check=True, capture_output=True, text=True)
    if result.stdout.strip() != lock['commit']:
        raise ValueError('Core-02 corpus checkout is not the pinned commit')
    package = root / lock['corpus_path']
    if not package.resolve().is_relative_to(root):
        raise ValueError('Corpus path escapes repository')
    manifest_path = package / 'manifest.json'
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != lock['manifest_sha256']:
        raise ValueError('Core-02 manifest does not match external pin')
    manifest = json.loads(raw)
    if manifest['expanded_corpus_sha256'] != lock['expanded_corpus_sha256']:
        raise ValueError('Expanded corpus pin mismatch')
    for name, digest in manifest['files'].items():
        if Path(name).name != name:
            raise ValueError('Unsafe corpus member')
        path = package / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen corpus source mismatch: ' + name)
    print(json.dumps({'status': 'PASS_PINNED_CHECKOUT', 'commit': lock['commit'],
                      'manifest_sha256': lock['manifest_sha256'],
                      'appraiser_executed': False}, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
