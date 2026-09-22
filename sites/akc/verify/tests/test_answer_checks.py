"""Natural answers and adversarial fact binding beyond the original fixtures."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from answer_checks import entity_blocks, event_date, named_fact, quantity_facts, rating, winner


class AnswerChecksTests(unittest.TestCase):
    def test_equivalent_ranges_and_exclusion(self):
        for text in [
            'It lives twelve to fifteen years and weighs thirteen to eighteen pounds.',
            'Weight: 13–18 lb; lifespan: 12–15 years.',
            'It lives between twelve and fifteen years and weighs between thirteen and eighteen pounds.',
            'Life expectancy 144–180 months. Weight 5.9–8.16 kg.',
            'Weight is 13–18 pounds, not 90 pounds. Life expectancy is 12–15 years.',
        ]:
            with self.subTest(text=text):
                self.assertTrue(quantity_facts(text, ['12-15 years','13-18 lb']))

    def test_wrong_units_properties_and_contradictions(self):
        for text in [
            'Weight 12-15 years; life expectancy 13-18 lb.',
            '112-15 years; 113-18 pounds.',
            'Life expectancy is not 12-15 years. Weight 13-18 pounds.',
            'Life expectancy is 12-15 years and 99 years. Weight 13-18 lb.',
            'Life expectancy 12-15 months; weight 13-18 kg.',
            'Life expectancy 2 years. Weight 90 lb. Reference: 12-15 years; 13-18 lb.',
        ]:
            with self.subTest(text=text):
                self.assertFalse(quantity_facts(text, ['12-15 years','13-18 lb']))

    def test_rating_scale_polarity_and_other_property(self):
        for text in ['energy four out of five','energy 4.0/5','energy 80%','energy: 4','energy 4/5, not 1/5','energy 4/5; grooming 5/5']:
            with self.subTest(text=text): self.assertTrue(rating(text,'energy',4))
        for text in ['energy 1/4','energy 4/10','energy not 4/5','energy 1/5 then 4/5','energy 4%','energy -4/5','energy 4 years','energy 4/banana','grooming 4/5']:
            with self.subTest(text=text): self.assertFalse(rating(text,'energy',4))

    def test_markdown_entity_binding(self):
        entities={'golden':['Golden Retriever'],'border':['Border Collie']}
        answer='| Breed | Energy |\n|---|---|\n| Golden Retriever | four out of five |\n| Border Collie | five out of five |\nBorder Collie is higher.'
        blocks=entity_blocks(answer,entities)
        self.assertTrue(rating(blocks['golden'],'energy',4))
        self.assertTrue(rating(blocks['border'],'energy',5))
        self.assertTrue(winner(answer,entities,'border'))

    def test_winner_direction_and_polarity(self):
        entities={'golden':['Golden Retriever'],'border':['Border Collie']}
        for answer in ['Border Collie is higher than Golden Retriever.', 'Golden Retriever is lower than Border Collie.', 'The highest breed is Border Collie.']:
            with self.subTest(answer=answer):self.assertTrue(winner(answer,entities,'border'))
        for answer in ['Border Collie is not higher.', 'Golden Retriever is higher than Border Collie.', 'Border Collie is higher. Golden Retriever is also highest.']:
            with self.subTest(answer=answer):self.assertFalse(winner(answer,entities,'border'))

    def test_author_and_date(self):
        self.assertTrue(named_fact('The author is Mina Brooks, not Randa Kriss.','Mina Brooks',['Mina Brooks','Randa Kriss']))
        self.assertFalse(named_fact('It is not by Mina Brooks.','Mina Brooks'))
        self.assertFalse(named_fact('The author is Randa Kriss. Reference: Mina Brooks.','Mina Brooks',['Randa Kriss']))
        for answer in ['27 Jun 2026','June 27th, 2026','06/27/2026','2026-06-27']:
            with self.subTest(answer=answer): self.assertTrue(event_date(answer,'2026-06-27'))
        for answer in ['Not June 27, 2026.','June 28, 2026 (reference: June 27, 2026)','June 27, 2026 and June 28, 2026']:
            with self.subTest(answer=answer):self.assertFalse(event_date(answer,'2026-06-27'))
