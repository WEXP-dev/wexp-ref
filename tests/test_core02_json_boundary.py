"""Local parser boundary tests. These are not a standardized WEXP carrier."""
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from wexp_ref.core02.qualify import read_json

class Core02JSONBoundary(unittest.TestCase):
    def test_explicit_nonfinite_constants(self):
        for raw in ('NaN', 'Infinity', '-Infinity'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                read_json(raw)
    def test_overflow_exponents(self):
        for raw in ('1e9999', '-1e9999', '{"x":1e9999}', '[1e9999]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                read_json(raw)
    def test_finite_numbers_remain_decoded(self):
        for raw in ('0', '1', '-1', '1e30', '-1e30', '1e-10'):
            with self.subTest(raw=raw):
                value=read_json(raw)
                self.assertTrue(math.isfinite(value))
    def test_json_boolean_is_not_number(self):
        self.assertIs(read_json('true'), True)
        self.assertIs(read_json('false'), False)
        self.assertIs(type(read_json('1')), int)
    def test_duplicate_object_keys(self):
        for raw in ('{"x":1,"x":2}', '{"v":{"x":1,"x":1}}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                read_json(raw)
    def test_invalid_json_and_encoding(self):
        for raw in (b'{', b'\xff', b'{"x":}'):
            with self.subTest(raw=raw), self.assertRaises((ValueError, UnicodeError)):
                read_json(raw)
    def test_cli_overflow_has_no_core_result(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'profiles.json').write_text('{}')
            for raw in ('1e9999', '-1e9999', '{"x":1e9999}'):
                (root/'input.json').write_text(raw)
                result=subprocess.run([sys.executable,'-B','-m','wexp_ref.core02',
                    '--input',str(root/'input.json'),'--profiles',str(root/'profiles.json')],
                    capture_output=True,text=True,timeout=10)
                with self.subTest(raw=raw):
                    self.assertEqual(result.returncode,2)
                    self.assertEqual(result.stdout,'')
                    error=json.loads(result.stderr)
                    self.assertFalse(error['core_appraisal_produced'])
                    self.assertNotIn('Traceback',result.stderr)
    def test_decoded_wrong_type_produces_core_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'profiles.json').write_text('{}')
            (root/'input.json').write_text('123')
            result=subprocess.run([sys.executable,'-B','-m','wexp_ref.core02',
                '--input',str(root/'input.json'),'--profiles',str(root/'profiles.json')],
                capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0)
            self.assertEqual(result.stderr,'')
            value=json.loads(result.stdout)
            self.assertEqual(value['fatal_reasons'],['E_MALFORMED_NORMALIZED_INPUT'])
            self.assertEqual(len(value),20)

if __name__=='__main__':
    unittest.main()
