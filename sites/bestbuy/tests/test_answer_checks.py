"""Natural equivalents and contradictory facts must grade differently."""
import importlib.util
from pathlib import Path
import unittest
spec = importlib.util.spec_from_file_location('answers', Path(__file__).resolve().parents[1] / 'verify/answer_checks.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)

class AnswerChecks(unittest.TestCase):
    def test_equivalents(self):
        cases = [
            (a.price, ('USD 549.99', 549.99)),
            (a.cheaper, ('HP costs $70 less than Dell.', 70)),
            (a.price, ('549 dollars and 99 cents', 549.99)),
            (a.rating, ('four and a half stars out of five', 4.5)),
            (a.rating, ('Rating: 4.9/5', 4.9)),
            (a.cheaper, ('HP OmniBook is seventy dollars cheaper than Dell.', 70)),
            (a.cheaper, ('Dell is more expensive by $70.', 70)),
            (a.rewards, ('1,840 points and zero certificates', 1840, 0)),
            (a.lenses, ('18 to 55 millimeters and 75 through 300 mm',)),
            (a.pickup_requirements, ('Bring an order number and photographic identification.',)),
            (a.pickup_status, ('Collected in store; status: delivered.',)),
            (a.savings, ('HP OmniBook: forty-five percent savings.', 45)),
        ]
        for fn,args in cases:
            with self.subTest(answer=args[0]): self.assertTrue(fn(*args))

    def test_wrong_values_scales_and_negations(self):
        cases = [
            (a.price, ('$1549.99', 549.99)),
            (a.price, ('$549.99; price is $499.99', 549.99)),
            (a.rating, ('4.9 out of 10', 4.9)),
            (a.rating, ('rating is not 4.9 stars', 4.9)),
            (a.cheaper, ('Dell is cheaper by $70.', 70)),
            (a.cheaper, ('HP is cheaper by $170.', 70)),
            (a.rewards, ('18400 points and 0 certificates', 1840, 0)),
            (a.lenses, ('18-55 cm and 75-300 cm',)),
            (a.lenses, ('Neither 18-55mm nor 75-300mm are included.',)),
            (a.pickup_requirements, ('Do not bring an order number or photo ID.',)),
            (a.pickup_status, ('Not pickup; not delivered.',)),
            (a.savings, ('HP OmniBook: 145%', 45)),
            (a.order_number, ('Not BBY-240003', 'BBY-240003')),
        ]
        for fn,args in cases:
            with self.subTest(answer=args[0]): self.assertFalse(fn(*args))
