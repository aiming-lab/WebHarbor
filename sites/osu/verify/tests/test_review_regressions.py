"""User-visible false accepts/rejects reproduced during the PR 120 review."""
import unittest

from _support import ensure_seed
import test_verifiers as fixtures
from test_verifiers import click, nav, trans


class ReviewRegressionTests(unittest.TestCase):
    run_verifier = fixtures.VerifierTests.run_verifier
    positive = fixtures.VerifierTests.positive

    @classmethod
    def setUpClass(cls):
        ensure_seed()

    def check_cases(self, expected, cases):
        for task, answer in cases:
            with self.subTest(task=task, answer=answer):
                steps, _ = self.positive(task)
                _, verdict = self.run_verifier(task, steps, answer)
                self.assertEqual(verdict['pass'], expected, verdict)

    def test_concise_and_equivalent_answers(self):
        self.check_cases(True, [
            (0, 'Anil Makhija.'),
            (1, '36.'),
            (1, 'There are thirty-six varsity sports.'),
            (2, 'Both pages list the Big Ten conference.'),
            (3, 'Ryan Day is head coach; the recent record is 11 wins and 2 losses.'),
            (4, 'Research expenditures were $1,300,000,000; published on 2024-09-23.'),
            (4, 'The expenditure amount was 1300 million dollars, published 23 September 2024.'),
            (9, 'BS, MS, and PhD: three distinct degree types.'),
            (9, 'I found three degree types: BS, MS, and PhD.'),
            (12, 'The JD requires 90 credits and takes three years.'),
            (12, 'JD; 90 credit hours; duration: 36 months.'),
            (16, 'The application deadline is 1 April; 60 credits; GRE: not required.'),
            (16, 'Deadline April 1st; 60 credits; GRE is optional.'),
        ])

    def test_values_must_describe_the_correct_fact(self):
        self.check_cases(False, [
            (4, 'Research expenditures were $1.3 million, below a billion dollars. September 23, 2024.'),
            (7, 'There are 14,000 undergraduates and 46,820 graduate students. Difference: 32,820.'),
            (7, 'There are 46,820 undergraduate students. Of these undergraduates, 14,000 live on campus. Difference: 32,820.'),
            (8, 'Engineering has 4,500 undergraduates and Fisher has 8,000. Fisher has more by 3,500.'),
            (8, 'Engineering has 8,000; Fisher has 4,500. Fisher has more by 3,500.'),
            (9, 'BS, MS, PhD, and BEng are the distinct types. There are 3 types.'),
            (9, 'BS, MS, PhD, and beng are the distinct types. There are 3 types.'),
            (9, 'BS, MS, and PhD: 4 distinct degree types; reference number 3.'),
            (12, 'The degree type is JD, requiring 3 credits over 90 years.'),
            (14, 'Football plays at Value City Arena and basketball plays at Ohio Stadium.'),
            (14, 'Football does not play at Ohio Stadium; basketball does not play at Value City Arena.'),
            (15, 'Wrestling has 2 national championships and fencing has 8. Fencing has more by 6.'),
            (15, 'Wrestling has 8 national championships; fencing has 2. Fencing has more by 6.'),
            (16, 'Deadline April 1; 60 credits. GRE is required; a portfolio is not required.'),
        ])

    def test_sentence_and_line_boundaries(self):
        for separator in ('. ', '; ', '\n', ' and '):
            self.check_cases(False, [(14, 'Football: Value City Arena' + separator + 'Basketball: Ohio Stadium.')])
            self.check_cases(True, [(14, 'Football: Ohio Stadium' + separator + 'Basketball: Value City Arena.')])

    def test_contradictory_claims_fail(self):
        self.check_cases(False, [
            (4, '$1.3 billion; $2.1 billion; September 23, 2024.'),
            (7, 'Undergraduates: 46820; graduates: 14000; difference: 32820. Undergraduates: 14000.'),
            (12, 'JD; 90 credits and 3 years. It requires 120 credits.'),
            (16, 'April 1; 60 credits; GRE not required. GRE is mandatory.'),
        ])

    def test_related_team_links_and_missing_visits(self):
        listing = '/athletics'
        football = listing + '/ohio-state-buckeyes-football'
        basketball = listing + '/ohio-state-buckeyes-mens-basketball'
        _, answer = self.positive(14)
        for first, second in ((football, basketball), (basketball, football)):
            steps = [nav(listing)] + trans(listing, first) + trans(first, second)
            _, verdict = self.run_verifier(14, steps, answer)
            self.assertTrue(verdict['pass'], verdict)
        # Visiting a detail directly then clicking its related link does not
        # establish the requested listing-rooted path, even if Athletics follows.
        for steps in (
            trans(football, basketball) + [nav(listing)],
            trans(listing, football),
            [nav(listing), nav(football), click(football, basketball)],
        ):
            _, verdict = self.run_verifier(14, steps, answer)
            self.assertFalse(verdict['pass'], verdict)

    def test_academics_does_not_require_a_homepage_click(self):
        _, verdict = self.run_verifier(0, [nav('/about')] + trans('/about', '/academics'), 'Anil Makhija.')
        self.assertTrue(verdict['pass'], verdict)
