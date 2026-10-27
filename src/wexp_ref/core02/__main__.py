"""Local JSON harness for normalized Core-02 inputs, not a standard wire format."""
import argparse
import json
from pathlib import Path
import sys
from .appraiser import appraise
from .qualify import read_json

MAX_BYTES = 4 * 1024 * 1024

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--profiles', type=Path, required=True)
    args = parser.parse_args()
    try:
        values = []
        for path in (args.input, args.profiles):
            with path.open('rb') as stream:
                raw = stream.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError('Local harness size limit exceeded')
            values.append(read_json(raw))
        value, profiles = values
        if type(profiles) is not dict:
            raise ValueError('Profile catalog must be an object')
    except (OSError, ValueError, RecursionError) as exc:
        print(json.dumps({'harness_error': str(exc), 'core_appraisal_produced': False}), file=sys.stderr)
        return 2
    output = appraise(value, profiles)
    print(json.dumps(output, sort_keys=True, ensure_ascii=True, allow_nan=False))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
