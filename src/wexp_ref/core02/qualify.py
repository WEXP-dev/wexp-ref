"""Compare complete Core-02 results with a separately pinned corpus."""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import platform
from .appraiser import appraise

SET_FIELDS = {'qualifiers', 'profile_identifiers', 'basis_refs', 'reasons',
              'limitations', 'base_findings', 'qualifier_findings',
              'recorder_relations', 'counter_evidence', 'evaluation_scope',
              'profile_evaluation_gaps', 'inherited_limitations', 'fatal_conditions',
              'affected_claims', 'fatal_reasons', 'substantive_reasons',
              'evaluation_gaps', 'evaluation_gap_entries', 'supported_claims',
              'maximal_supported_claims', 'support_entries', 'support_relations'}

def encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)

def logical(value, field=None):
    if type(value) is dict:
        return {key: logical(item, key) for key, item in value.items()}
    if type(value) is list:
        items = [logical(item) for item in value]
        return sorted(items, key=encoded) if field in SET_FIELDS else items
    return value

def same(left, right):
    # JSON representation distinguishes bool from int; never deduplicate values.
    return encoded(logical(left)) == encoded(logical(right))

def sha(value):
    return hashlib.sha256(encoded(logical(value)).encode('ascii')).hexdigest()

def strict_pairs(items):
    obj = {}
    for key, value in items:
        if key in obj:
            raise ValueError('Duplicate JSON object member: ' + key)
        obj[key] = value
    return obj

def forbidden_constant(value):
    raise ValueError('Non-finite JSON constant: ' + value)

def finite_float(text):
    """Reject exponent overflow as a harness decoding failure, never Core evidence."""
    value = float(text)
    if not math.isfinite(value):
        raise ValueError('JSON number is outside the finite local representation')
    return value

def read_json(raw):
    return json.loads(raw, object_pairs_hook=strict_pairs,
                      parse_constant=forbidden_constant, parse_float=finite_float)

def qualify(corpus_path, expected_sha256):
    raw = Path(corpus_path).read_bytes()
    actual_hash = hashlib.sha256(raw).hexdigest()
    if actual_hash != expected_sha256:
        raise ValueError('Corpus does not match the externally pinned digest')
    corpus = read_json(raw)
    if corpus.get('semantics_version') != 'wexp-core-2':
        raise ValueError('Wrong corpus semantics')
    results = []
    for case in corpus['cases']:
        value = deepcopy(case['input'])
        profiles = deepcopy(case.get('profiles', corpus['profiles']))
        before_profiles = deepcopy(profiles)
        observed = appraise(value, profiles)
        expected = case['expected']
        equal = same(observed, expected)
        immutable = same(value, case['input']) and same(profiles, before_profiles)
        results.append({'id': case['id'], 'equal_full_result': equal,
                        'input_and_configuration_unchanged': immutable,
                        'expected_sha256': sha(expected),
                        'observed_sha256': sha(observed),
                        'observed': observed})
    sample = corpus['cases'][0]['expected']
    controls = []
    for field in sample:
        dropped = deepcopy(sample)
        del dropped[field]
        changed = deepcopy(sample)
        changed[field] = {'invalid-comparator-control': True}
        controls.extend([not same(sample, dropped), not same(sample, changed)])
    for boolean in (True, False):
        sample = next(case['expected'] for case in corpus['cases']
                      if case['expected']['asserted_claim_supported'] is boolean)
        changed = deepcopy(sample)
        changed['asserted_claim_supported'] = int(boolean)
        controls.append(not same(sample, changed))
    passed = all(row['equal_full_result'] and row['input_and_configuration_unchanged']
                 for row in results) and all(controls)
    return {'status': 'PASS_BOUNDED' if passed else 'FAIL',
            'semantics_version': 'wexp-core-2',
            'python': platform.python_version(),
            'platform': platform.platform(),
            'corpus_sha256': actual_hash,
            'appraiser_sha256': hashlib.sha256(Path(__file__).with_name('appraiser.py').read_bytes()).hexdigest(),
            'case_count': len(results),
            'passed': sum(row['equal_full_result'] and row['input_and_configuration_unchanged'] for row in results),
            'components_per_result': 20,
            'comparator_negative_controls_passed': sum(controls),
            'comparator_negative_controls_total': len(controls),
            'independent_external_validation': False,
            'full_conformance_claimed': False,
            'carrier_or_mapping_conformance_claimed': False,
            'coverage_conformance_claimed': False,
            'results': results}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--corpus', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = qualify(args.corpus, args.expected_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, ensure_ascii=True)
        stream.write('\n')
    print(encoded({key: value for key, value in report.items() if key != 'results'}))
    return 0 if report['status'] == 'PASS_BOUNDED' else 1

if __name__ == '__main__':
    raise SystemExit(main())
