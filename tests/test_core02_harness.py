"""Bounded Core-02 ingress and local harness regressions; not conformance."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from wexp_ref.core02 import appraise
from wexp_ref.core02.qualify import read_json, same

CAPS = ('carrier-mapping', 'authenticity', 'target-binding', 'boundary-grounding',
        'observation-support', 'intent-support', 'invocation-support',
        'execution-support', 'provenance-support', 'independent-verification',
        'composition', 'counter-evidence')


def fixture():
    common = {'target': 'T', 'evaluation_context_ref': 'C',
              'target_binding': 'supported', 'basis_refs': [],
              'reasons': [], 'limitations': []}
    return {
        'semantics_version': 'wexp-core-2', 'target': 'T',
        'asserted_claim': {'base': 'intent', 'qualifiers': []},
        'evaluation_context': {'id': 'C', 'evaluated_at': 'fixed-test-time',
                               'trust_configuration': 'attributed-test-boundary',
                               'profile_identifiers': []},
        'boundary_finding': {**deepcopy(common), 'status': 'supported',
                             'grounding': 'attributed', 'ceiling_base': 'intent'},
        'base_findings': [{**deepcopy(common), 'base': 'intent',
                           'semantic_validation': 'supported'}],
        'qualifier_findings': [], 'recorder_relations': [],
        'counter_evidence': [{'status': 'not-supplied', 'affected_claims': [],
                              'basis_refs': [], 'reasons': [], 'limitations': []}],
        'evaluation_scope': [{'capability': c, 'status': 'evaluated'} for c in CAPS],
        'profile_evaluation_gaps': [], 'inherited_limitations': [],
        'fatal_conditions': []}


class Core02HarnessTests(unittest.TestCase):
    def test_complete_result_and_unchanged_input(self):
        value = fixture()
        before = deepcopy(value)
        actual = appraise(value, {})
        self.assertEqual(actual['verdict'], 'accept')
        self.assertEqual(len(actual), 20)
        self.assertEqual(actual['supported_claims'], [{'base': 'intent', 'qualifiers': []}])
        self.assertEqual(value, before)

    def test_unsupported_version_precedes_member_checks(self):
        result = appraise({'semantics_version': 'wexp-core-1', 'unknown': 1})
        self.assertEqual(result['fatal_reasons'], ['E_UNSUPPORTED_SEMANTICS_VERSION'])
        self.assertEqual(len(result), 20)
        self.assertIsNone(result['target'])

    def test_extension_shape_precedes_mapping(self):
        value = fixture()
        value['base_findings'][0]['target'] = 'foreign'
        value['evaluation_scope'].append({'capability': [], 'status': 'evaluated'})
        self.assertEqual(appraise(value)['fatal_reasons'], ['E_MALFORMED_NORMALIZED_INPUT'])

    def test_valid_shape_unbound_extension_is_mapping_error(self):
        value = fixture()
        value['evaluation_scope'].append({'capability': ['unbound', 'x'], 'status': 'evaluated'})
        self.assertEqual(appraise(value)['fatal_reasons'], ['E_PROFILE_MAPPING_INVALID'])

    def test_comparator_preserves_types_ordered_atoms_and_multiplicity(self):
        for left, right in [({'value': True}, {'value': 1}),
                            ({'basis_refs': [['a', 'b']]}, {'basis_refs': [['b', 'a']]}),
                            ({'qualifiers': ['IV']}, {'qualifiers': ['IV', 'IV']})]:
            with self.subTest(left=left):
                self.assertFalse(same(left, right))
        self.assertTrue(same({'qualifiers': ['IV', 'PROV']}, {'qualifiers': ['PROV', 'IV']}))

    def test_strict_parser(self):
        for text in ('{', '{"a":1,"a":2}', 'NaN', 'Infinity'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                read_json(text)

    def test_cli_normal_and_optimized(self):
        cases = [('accept', json.dumps(fixture()), 0, 'accept'),
                 ('syntax', '{', 2, None),
                 ('duplicate', '{"semantics_version":"a","semantics_version":"b"}', 2, None),
                 ('nonfinite', 'NaN', 2, None),
                 ('oversize', ' ' * (4 * 1024 * 1024 + 1), 2, None),
                 ('malformed', '{"semantics_version":"wexp-core-2"}', 0, 'reject'),
                 ('unsupported', '{"semantics_version":"wexp-core-1"}', 0, 'reject')]
        with tempfile.TemporaryDirectory(prefix='core02-harness-') as directory:
            root = Path(directory)
            profiles = root / 'profiles.json'
            profiles.write_text('{}', encoding='utf-8')
            for optimized in (False, True):
                for name, text, exit_code, verdict in cases:
                    with self.subTest(case=name, optimized=optimized):
                        source = root / (name + '.json')
                        source.write_text(text, encoding='utf-8')
                        command = [sys.executable, '-B'] + (['-O'] if optimized else [])
                        run = subprocess.run(command + ['-m', 'wexp_ref.core02', '--input',
                            str(source), '--profiles', str(profiles)],
                            capture_output=True, text=True, timeout=15)
                        self.assertEqual(run.returncode, exit_code, run.stderr)
                        if verdict is None:
                            self.assertEqual(run.stdout, '')
                            self.assertIs(json.loads(run.stderr)['core_appraisal_produced'], False)
                        else:
                            actual = json.loads(run.stdout)
                            self.assertEqual(actual['verdict'], verdict)
                            self.assertEqual(len(actual), 20)


if __name__ == '__main__':
    unittest.main()
