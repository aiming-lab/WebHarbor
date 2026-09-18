"""Read-only multi-page contracts, independent of downloaded asset databases."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1]))
from deterministic import Review
from rules import evaluate


GOOD = {
    12: "2019 Nissan Altima SV: offer $14,750, expiry 2026-05-20. "
        "Written offer validity: 7 days. An online offer requires in-store verification. "
        "The price is the same whether selling outright or trading in.",
    16: "Bob's APR: 5.49%. Loan term: 60 months. Down payment: $5,000. "
        "Expiry: 2026-06-13. Policy validity: 30 days. "
        "Pre-qualification uses a soft credit inquiry that does not impact your credit score, "
        "whereas a final credit application uses a hard inquiry.",
    19: "Order CMX-2026-000001: 2023 Toyota Tacoma TRD Sport. "
        "Current ordered MaxCare: Gold, $1,895.\n"
        "Silver: $1,495, 36 months, 50,000 miles.\n"
        "Gold: $1,895, 48 months, 75,000 miles.\n"
        "Platinum: $2,395, 60 months, 100,000 miles.\n"
        "Upgrade Gold to Platinum: additional $500, 12 months, 25,000 miles.\n"
        "Rental reimbursement: $40/day. Coverage includes Canada.",
}


def review(task, answer, missing_path='', mutate=False):
    r = Review.__new__(Review)
    r.task, r.answer, r.evidence, r.failures = task, answer, [], []
    r.initial = {
        'users': [
            dict(id=3, email='carol.l@test.com'),
            dict(id=2, email='bob.k@test.com', pre_qual_apr=5.49,
                 pre_qual_term_months=60, pre_qual_down_payment=5000,
                 pre_qual_expires_at='2026-06-13'),
            dict(id=4, email='dan.m@test.com'),
        ],
        'appraisals': [dict(user_id=3, status='active', year=2019, make='Nissan',
                            model='Altima', trim='SV', offer_amount=14750,
                            offer_valid_until='2026-05-20')],
        'vehicles': [dict(id=10, year=2023, make='Toyota', model='Tacoma', trim='TRD Sport')],
        'orders': [dict(user_id=4, vehicle_id=10, order_number='CMX-2026-000001',
                        maxcare_plan='gold', maxcare_price=1895)],
        'articles': [dict(title='Getting Pre-Qualified: Shop with Personalized Financing Terms',
                          slug='getting-pre-qualified')],
    }
    r.expected = deepcopy(r.initial)
    r.after = deepcopy(r.initial)
    r.nav = lambda path, query=None: missing_path not in path if missing_path else True
    if mutate:
        r.after['users'][0]['email'] = 'changed@test.com'
    evaluate(r)
    return r.finish()


class DifficultyContracts(unittest.TestCase):
    def test_complete_answers_and_read_only_state(self):
        for task, answer in GOOD.items():
            with self.subTest(task=task):
                self.assertTrue(review(task, answer)['pass'])
                self.assertFalse(review(task, answer, mutate=True)['pass'])

    def test_each_required_source_is_required(self):
        paths = {12: ['account/appraisals', 'how-long', 'can-i-get'],
                 16: ['pre-qual/result', 'articles/', 'faq/financing'],
                 19: ['order/', 'maxcare-service-plans', 'faq/warranty']}
        for task, parts in paths.items():
            for part in parts:
                with self.subTest(task=task, path=part):
                    self.assertFalse(review(task, GOOD[task], missing_path=part)['pass'])

    def test_old_single_page_answers_rejected(self):
        old = {12: '7 days.', 16: GOOD[16].split('Pre-qualification')[1],
               19: '\n'.join(GOOD[19].splitlines()[1:4])}
        for task, answer in old.items():
            self.assertFalse(review(task, answer)['pass'])

    def test_missing_and_wrong_facts(self):
        replacements = {
            12: [(' SV', ''), ('$14,750', '$14,570'), ('2026-05-20', '2026-05-21'),
                 ('7 days', '30 days'), ('requires in-store verification', 'needs no in-store verification'),
                 ('same', 'not the same')],
            16: [('5.49%', '7.49%'), ('60 months', '72 months'), ('$5,000', '$2,500'),
                 ('2026-06-13', '2026-06-14'), ('30 days', '30 months'),
                 ('soft credit inquiry', 'hard credit inquiry')],
            19: [('TRD Sport', 'TRD Off-Road'), ('Gold, $1,895', 'Silver, $1,495'),
                 ('$500', '$400'), ('12 months', '12 days'), ('25,000 miles', '25,000 kilometers'),
                 ('36 months', '48 months'), ('$40/day', '$40/month'),
                 ('includes Canada', 'does not include Canada')],
        }
        for task, pairs in replacements.items():
            for old, new in pairs:
                with self.subTest(task=task, replacement=(old, new)):
                    self.assertFalse(review(task, GOOD[task].replace(old, new))['pass'])

    def test_equivalent_formatting(self):
        answers = {
            12: GOOD[12].replace('$14,750', '14750 dollars').replace('2026-05-20', 'May 20, 2026')
                .replace('7 days', 'seven days').replace('same', 'unchanged'),
            16: GOOD[16].replace('5.49%', '5.49 percent').replace('$5,000', '5000 USD')
                .replace('2026-06-13', '13 June 2026').replace('30 days', 'thirty days'),
            19: GOOD[19].replace('months', 'mo').replace('miles', 'mi')
                .replace('100,000', '100k').replace('$500', '500 dollars')
                .replace('$40/day', '40 dollars per day'),
        }
        for task, answer in answers.items():
            with self.subTest(task=task):
                self.assertTrue(review(task, answer)['pass'], review(task, answer)['reason'])


if __name__ == '__main__':
    unittest.main()
