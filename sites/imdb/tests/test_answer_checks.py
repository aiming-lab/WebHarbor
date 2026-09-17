"""Synthetic answer-parser boundary cases; these are not browser runs."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'verify'))
from answer_checks import (displayed_money, entity_texts, has_amount, has_date,
                           has_number, mentions, money_field)


class AnswerChecksTests(unittest.TestCase):
    def test_equivalent_units_and_exact_value(self):
        for answer in ('$250.9M', 'USD 250.9 million', '$250,933,053'):
            with self.subTest(answer=answer):
                self.assertTrue(has_amount(answer, 250933053))
        self.assertFalse(has_amount('$250M', 250933053))
        self.assertFalse(has_amount('$250.9M or $250M', 250933053))

    def test_field_binding_in_either_direction(self):
        for answer in ('Budget: $25M; opening weekend: $727.3K',
                       '$25 million budget and $727,327 opening weekend'):
            with self.subTest(answer=answer):
                self.assertTrue(money_field(answer, 'budget', 25000000))
                self.assertTrue(money_field(answer, 'opening', 727327))
        swapped = 'Budget: $727.3K; opening weekend: $25M'
        self.assertFalse(money_field(swapped, 'budget', 25000000))
        self.assertFalse(money_field(swapped, 'opening', 727327))

    def test_year_does_not_masquerade_as_money(self):
        self.assertTrue(has_amount('The Godfather (1972): $250.9M', 250933053))
        self.assertFalse(has_amount('The Godfather (1972)', 1972))

    def test_rows_and_columns_bind_entities(self):
        entities = {'a': ['The Dark Knight'], 'b': ['Inception']}
        tables = [
            '| Title | IMDb rating | Worldwide gross |\n|---|---|---|\n'
            '| The Dark Knight | 9.1 | $1.0B |\n| Inception | 8.8 | $839.8M |',
            '| Field | The Dark Knight | Inception |\n|---|---|---|\n'
            '| IMDb rating | 9.1 | 8.8 |\n| Worldwide gross | $1.0B | $839.8M |',
        ]
        for table in tables:
            with self.subTest(table=table):
                records = entity_texts(table, entities)
                self.assertTrue(has_number(records['a'], 9.1))
                self.assertFalse(has_number(records['a'], 8.8))
                self.assertTrue(money_field(records['b'], 'worldwide', 839796627))
                self.assertFalse(money_field(records['a'], 'worldwide', 839796627))

    def test_dates_and_negation(self):
        self.assertTrue(has_date('May 26, 2026', '2026-05-26'))
        self.assertTrue(has_date('26 May 2026', '2026-05-26'))
        self.assertFalse(has_date('May 25, 2026', '2026-05-26'))
        self.assertTrue(mentions('Christian Bale as Bruce Wayne', 'Christian Bale'))
        self.assertFalse(mentions('It is not Christian Bale', 'Christian Bale'))
        self.assertFalse(mentions('Christian Baleish', 'Christian Bale'))

    def test_sentence_final_number_and_decimal_boundaries(self):
        self.assertTrue(has_number('Born in 1974.', 1974))
        self.assertTrue(has_number('IMDb rating: 9.0.', 9))
        self.assertFalse(has_number('IMDb rating: 9.01.', 9))
        self.assertFalse(has_number('Code x1974y', 1974))


if __name__ == '__main__':
    unittest.main()
