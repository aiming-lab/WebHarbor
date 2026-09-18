import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('carmax_deterministic', Path(__file__).parents[1]/'deterministic.py')
grading = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grading)


class AnswerPrimitiveTests(unittest.TestCase):
    def test_currency_with_sentence_punctuation(self):
        for answer in ['$15,300.', '$15300, mileage 58,626 mi.', '15300 dollars']:
            self.assertTrue(grading.money(answer, 15300), answer)

    def test_currency_is_not_mileage_or_reference(self):
        for answer in ['price $58,626; mileage 15,300 mi', 'reference 15300', '$115300']:
            self.assertFalse(grading.money(answer, 15300), answer)

    def test_units_and_boundaries(self):
        self.assertTrue(grading.measure('60 months, 100,000 miles', 100000, 'miles|mi'))
        self.assertFalse(grading.measure('100,000 kilometers', 100000, 'miles|mi'))
        self.assertFalse(grading.measure('112 states', 12, 'states'))

    def test_label_binding(self):
        self.assertTrue(grading.field('RepairPal reliability: 3.5', 'repairpal reliability', 3.5))
        self.assertTrue(grading.field('3.5\nRepairPal reliability', 'repairpal reliability', 3.5))
        self.assertFalse(grading.field('RepairPal reliability: 4.5; customer rating: 3.5', 'repairpal reliability', 3.5))

    def test_dates(self):
        for answer in ['May 21, 2026', '2026-05-21', '21 May 2026', '5/21/2026']:
            self.assertTrue(grading.date_in(answer, '2026-05-21'), answer)
        self.assertFalse(grading.date_in('May 22, 2026', '2026-05-21'))

    def test_missing_snapshot_fails_without_creating_a_database(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'absent.db'
            with self.assertRaises(ValueError):
                grading.snapshot(path)
            self.assertFalse(path.exists())


if __name__ == '__main__':
    unittest.main()
