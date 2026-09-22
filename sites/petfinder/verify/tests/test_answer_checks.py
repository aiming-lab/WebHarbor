"""Meaning-preserving answer variants and adversarial association controls."""
import unittest

from answer_checks import checklist, inquiry_submitted, no_duplicate, numeric_fact, winner


class AnswerChecksTests(unittest.TestCase):
    def test_comparison_values_bind_to_their_pet(self):
        good = [
            'Ollie: 5 days; Maple: 18 days.',
            'With only 5 days, Ollie has fewer days than Maple, which has 18 days.',
            'Ollie has been listed for less time: 5 days, compared with 18 days for Maple.',
            '| Pet | Days |\n| Ollie | 5 |\n| Maple | 18 |',
        ]
        bad = [
            'Ollie: 18 days; Maple: 5 days.',
            'Ollie: 50 days; Maple: 18 days. Reference 5.',
            'Ollie: 5 days; Maple: 18 days. Ollie actually has 6 days.',
            'Ollie: 5 dollars; Maple: 18 days.',
        ]
        for answer in good + bad:
            with self.subTest(answer=answer):
                passed = all(numeric_fact(answer, n, 'days', pet, ['Ollie', 'Maple']) for pet, n in [('Ollie', 5), ('Maple', 18)])
                self.assertEqual(passed, answer in good)

    def test_prices_require_currency_or_fee_context(self):
        for answer in ['The adoption fee is $75.', 'Fee: 75 dollars.', 'Adoption fee: 75.00 USD.']:
            self.assertTrue(numeric_fact(answer, 75, 'fee'), answer)
        for answer in ['Adoption fee is $999. Reference 75.', 'Fee: 75 cents.', 'Fee: $750.', 'Fee: $75.50.', 'Fee: $75. Fee: $80.', 'Fee is not $75.']:
            self.assertFalse(numeric_fact(answer, 75, 'fee'), answer)

    def test_winner_is_an_assertion_about_the_correct_pet(self):
        for answer in ['Ollie has fewer days than Maple.', 'Ollie has been listed for less time: 5 days; Maple: 18 days.', 'Fewest days: Ollie. Maple has 18.']:
            self.assertTrue(winner(answer, 'Ollie', ['Ollie', 'Maple'], 'days'), answer)
        for answer in ['Maple has fewer days; Ollie has 5.', 'Ollie does not have fewer days.', 'Ollie has fewer days. Maple has fewer days too.']:
            self.assertFalse(winner(answer, 'Ollie', ['Ollie', 'Maple'], 'days'), answer)
        self.assertTrue(winner('Scout is the cheapest to adopt.', 'Scout', ['Scout', 'Ace', 'Phoebe'], 'fee'))

    def test_counts_accept_words_and_reject_other_units(self):
        for answer in ['There are two favorite pets.', 'Favorite pets (2)', 'The total remains 2 favorites.']:
            self.assertTrue(numeric_fact(answer, 2, 'count'), answer)
        for answer in ['There are 9 favorites. Reference 2.', 'Favorite pets: $2.', 'There are not 2 favorites.']:
            self.assertFalse(numeric_fact(answer, 2, 'count'), answer)

    def test_adoption_checklist_paraphrases_and_omissions(self):
        good = 'Choose a vet and keep their clinic phone number handy; prepare a quiet room with food, water and a comfy bed; inspect fences, windows, plants and other hazards around the home.'
        self.assertTrue(checklist(good, 'adoption'))
        self.assertFalse(checklist(good.replace('water and ', ''), 'adoption'))
        self.assertFalse(checklist(good.replace('inspect fences', 'do not inspect fences'), 'adoption'))

    def test_rabbit_checklist_paraphrase(self):
        good = 'Prepare a rabbit-friendly space. Provide unlimited grass hay; protect cords and unsafe baseboards; add a hideaway and slip-resistant flooring.'
        self.assertTrue(checklist(good, 'rabbit'))
        self.assertFalse(checklist(good.replace('unlimited', 'limited'), 'rabbit'))

    def test_status_and_duplicate_claims_cannot_contradict_outcome(self):
        for answer in ['The inquiry status is Submitted.', 'Submitted, not rejected.']:
            self.assertTrue(inquiry_submitted(answer), answer)
        for answer in ['Submitted? No, it was rejected.', 'Not submitted.', 'Submitted; status is pending.']:
            self.assertFalse(inquiry_submitted(answer), answer)
        for answer in ['Milo was saved before this attempt, so nothing was added.', 'Already in favorites; no duplicate was added.']:
            self.assertTrue(no_duplicate(answer), answer)
        self.assertFalse(no_duplicate('Milo was already in favorites. A duplicate favorite was added.'))
