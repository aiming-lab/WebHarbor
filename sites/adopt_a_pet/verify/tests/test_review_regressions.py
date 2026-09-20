"""Controls for demonstrated review failures and natural positive equivalents."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_lib as V

class ReviewRegressions(unittest.TestCase):
    def test_complete_fee_and_property(self):
        for answer in ('two hundred twenty-five dollars and ninety-nine cents', '$225.99', 'USD 225.99', '$2250', 'fee $999; donation $225', 'fee $225; fee $999', 'donation $225', '$225 donation', '$225abc'):
            with self.subTest(answer=answer): self.assertFalse(V.contains_money(answer,225))
        for answer in ('$225.00', 'two hundred twenty-five dollars', 'two hundred and twenty five dollars', 'fee $225; donation $999', 'fee $225, not $999'):
            with self.subTest(answer=answer): self.assertTrue(V.contains_money(answer,225))

    def test_natural_months(self):
        for answer in ('seven months', 'seven-month-old', 'age: 7 months'):
            with self.subTest(answer=answer): self.assertTrue(V.contains_months(answer,7))
        for answer in ('seventy seven months', '7.5 months', '7 dollars', '7 months; actually 8 months'):
            with self.subTest(answer=answer): self.assertFalse(V.contains_months(answer,7))

    def test_entity_binding(self):
        names=['Daisy','Pepper']
        for answer in ('Daisy: dog, 30 months, $275. Pepper: cat, 13 months, $130.', 'Pet | Species | Age | Fee\nDaisy | dog | thirty months | $275\nPepper | cat | thirteen months | $130', 'Daisy (dog, 30 months, $275) is more expensive than Pepper (cat, 13 months, $130).'):
            with self.subTest(answer=answer):
                d=V.entity_text(answer,'Daisy',names);p=V.entity_text(answer,'Pepper',names)
                self.assertTrue(V.contains_money(d,275) and V.contains_money(p,130))
                self.assertTrue(V.contains_months(d,30) and V.contains_months(p,13))
                self.assertTrue(V.pet_species(d,'Dog') and V.pet_species(p,'Cat'))
        for answer in ('Daisy: cat, 13 months, $130. Pepper: dog, 30 months, $275.', 'Daisy: dog, 30 months, $275. Pepper: cat, 13 months, $130. Daisy costs $130.'):
            with self.subTest(answer=answer): self.assertFalse(V.contains_money(V.entity_text(answer,'Daisy',names),275))

    def test_comparison_polarity_and_conflicts(self):
        for answer in ('Pepper is not cheaper than Daisy.', 'Pepper is cheaper than Daisy. Daisy is cheaper than Pepper.', 'Pepper is cheaper and Daisy is cheaper.', 'The cheaper pet is not Pepper.', 'Pepper is cheaper. Pepper is more expensive.'):
            with self.subTest(answer=answer): self.assertFalse(V.identifies(answer,'Pepper',['Daisy'],V.LOWEST,V.HIGHEST))
        self.assertFalse(V.identifies('Batman does not have the lowest adoption fee. Batman $165.','Batman',['Sirius'],V.LOWEST,V.HIGHEST))
        for answer in ('Pepper is cheaper than Daisy.', 'Daisy is more expensive than Pepper.', 'The cheaper pet is Pepper.'):
            with self.subTest(answer=answer): self.assertTrue(V.identifies(answer,'Pepper',['Daisy'],V.LOWEST,V.HIGHEST))

    def test_duplicate_filters_follow_first_value(self):
        def traj(query,path='/search'): return {'steps':[{'url':'http://localhost:44912'+path+'?'+query}]}
        self.assertFalse(V.search_visited(traj('species=Cat&species=Dog'),species='Dog'))
        self.assertTrue(V.search_visited(traj('species=Dog&species=Cat'),species='Dog'))
        self.assertFalse(V.search_visited(traj('location=Miami&location=Phoenix'),location_any=[{'phoenix'}]))
        self.assertFalse(V.search_visited(traj('sex=Female&sex=Male'),sex='Male'))
        self.assertFalse(V.search_visited(traj('breed=Siamese&breed=Chihuahua'),breed='Chihuahua'))
        self.assertFalse(V.shelters_search_visited(traj('q=Miami&q=Seattle','/shelters'),[{'seattle'}]))
