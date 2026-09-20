"""Targeted T7 regressions; no full SQLite suite or native rollout."""
import importlib.util
from pathlib import Path
import unittest

SITE = Path(__file__).resolve().parents[1]


class T7BandwidthRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('t7_answers', SITE/'verify/answers.py')
        cls.answers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.answers)

    def test_shared_direction_unchanged(self):
        self.assertTrue(self.answers.direction('RTX 5090 has more CUDA cores than RTX 4090', '5090', '4090', 'cuda'))
        self.assertFalse(self.answers.direction('RTX 4090 has more CUDA cores than RTX 5090', '5090', '4090', 'cuda'))


ACTUAL = ('The GeForce RTX 5080 has higher memory bandwidth: 960 GB/s, compared with '
          '736 GB/s for the GeForce RTX 4080 SUPER. That is 224 GB/s (about 30.4%) higher.')
CASES = {
    'actual_native_answer': (ACTUAL, True),
    'winner_only': ('RTX 5080', True),
    'winner_without_values': ('RTX 5080 has higher memory bandwidth than RTX 4080 SUPER.', True),
    'absolute_values_only': ('RTX 5080 has higher bandwidth: 960 GB/s; RTX 4080 SUPER: 736 GB/s.', True),
    'postfix_attribution': ('RTX 5080 has higher bandwidth. 960 GB/s for the RTX 5080; 736 GB/s for the RTX 4080 SUPER.', True),
    'delta_only': ('RTX 5080 has higher bandwidth by 224 GB/s.', True),
    'labelled_gap': ('RTX 5080 has higher bandwidth. The difference is 224 GB/s.', True),
    'subject_then_delta': ('RTX 5080 has 224 GB/s more memory bandwidth than RTX 4080 SUPER.', True),
    'rounded_integer_percent': ('RTX 5080 has about 30% higher memory bandwidth than RTX 4080 SUPER.', True),
    'rounded_two_digits': (ACTUAL.replace('30.4%', '30.43%'), True),
    'rounded_three_digits': (ACTUAL.replace('30.4%', '30.435%'), True),
    'inverse_percentage': ('RTX 4080 SUPER has 23.3% lower memory bandwidth than RTX 5080.', True),
    'wrong_winner': ('RTX 4080 SUPER has higher memory bandwidth than RTX 5080.', False),
    'swapped_assignment': ('RTX 5080 has higher bandwidth: 736 GB/s; RTX 4080 SUPER: 960 GB/s.', False),
    'wrong_delta': (ACTUAL.replace('224 GB/s', '225 GB/s'), False),
    'wrong_percent': (ACTUAL.replace('30.4%', '31.4%'), False),
    'wrong_rounding': (ACTUAL.replace('30.4%', '30.5%'), False),
    'wrong_denominator': (ACTUAL.replace('30.4%', '23.3%'), False),
    'delta_as_absolute': ('RTX 5080 has higher bandwidth: 224 GB/s; RTX 4080 SUPER: 736 GB/s.', False),
    'extra_contradictory_claim': (ACTUAL + ' RTX 5080 has 736 GB/s.', False),
    'wrong_unit': (ACTUAL.replace('224 GB/s', '224 MB/s'), False),
    'wrong_target': ('RTX 5080 has higher memory bandwidth than RTX 4090.', False),
}
for label, (text, expected) in CASES.items():
    def test(self, answer=text, result=expected):
        self.assertIs(self.answers.bandwidth_comparison(answer, 960, 736), result)
    setattr(T7BandwidthRegression, 'test_' + label, test)
