"""Outcome controls for natural answers, independent of browser harness fixtures."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from answers import answer_ok

FIXTURE = {'authors': [{'id': 1, 'slug': 'lucia-ferreira-md'}],
           'articles': [{'reviewer_id': 1} for _ in range(5)],
           'users': [{'id': 1, 'email': 'carol.w@test.com'}],
           'saved_articles': [{'user_id': 1} for _ in range(4)]}

CASES = [
 (0, True, 'Miguel Santana, MD'),
 (0, True, 'Miguel Santana reviewed it, not Danielle Hart.'),
 (0, False, 'It was not Miguel Santana; Danielle Hart reviewed it.'),
 (1, True, 'Publication date: 2024-12-23\nReviewed: 27 December 2024'),
 (1, True, '| Published | December 23, 2024 |\n| Reviewed | December 27, 2024 |'),
 (1, False, 'Published December 27, 2024; reviewed December 23, 2024.'),
 (2, True, 'Written by Sofia Andersson and medically reviewed by Danielle Hart, MD.'),
 (2, True, 'Author: Sofia Andersson\nReviewer: Danielle Hart, MD'),
 (2, True, 'Sofia Andersson wrote it. Danielle Hart reviewed it.'),
 (2, False, 'Author: Danielle Hart; Reviewer: Sofia Andersson.'),
 (3, True, 'Author: Sofia Andersson; Reviewer: Karen Shale; Topic: Healthy Living.'),
 (3, False, 'Author: Karen Shale; Reviewer: Sofia Andersson; Topic: Healthy Living.'),
 (4, True, 'Start at 0.4 mg once a day, about half an hour after the same meal each day.'),
 (4, True, 'Starting dose: 400 micrograms once daily. Timing: thirty minutes after the same meal each day.'),
 (4, False, '0.4 mg three times daily, 30 minutes after the same meal each day.'),
 (4, False, '0.4 mg once daily, 30 minutes before the same meal each day.'),
 (4, False, '0.8 mg once daily; reference 0.4. Take 30 minutes after the same meal each day.'),
 (5, True, 'Steven Marsh reviewed the article. Credentials: PharmD, BCPS.'),
 (5, False, 'Steven Marsh is not the reviewer. PharmD, BCPS.'),
 (6, True, 'Ciprofloxacin, azithromycin, and amoxicillin.'),
 (6, False, 'Ciprofloxacin, azithromycin, amoxicillin, and rifampin.'),
 (7, True, 'Hormones & Thyroid; overactive thyroid and underactive thyroid.'),
 (7, False, 'Hormones & Thyroid; not hyperthyroidism or hypothyroidism.'),
 (8, True, 'Maximum 200 milligrams per day. Wait at least two hours before a second dose.'),
 (8, True, 'Max dose: 0.2 g in 24 hours; repeat interval: at least 2 hours.'),
 (8, False, 'Maximum 200 grams in 24 hours. Wait at least 2 hours.'),
 (8, False, 'Maximum 200 mg in 24 hours. Wait at least 1 hour, not 2 hours.'),
 (9, True, '5 mg twice a day. Reduced dose criteria: age 80 or older, body weight 60 kg or less, elevated creatinine.'),
 (9, True, 'Standard AFib dose: 5 mg twice daily. Reduced dose: age >= 80, weight <= 60 kg, high serum creatinine.'),
 (9, False, '2.5 mg twice daily; age under 80, weight above 60 kg, low creatinine.'),
 (9, False, '5 mg twice daily. Criteria: not age 80 or older, not weight 60 kg or less, not elevated creatinine.'),
 (10, True, 'Hydrochlorothiazide; Curtis Boone wrote the article.'),
 (11, True, 'The Epley maneuver and ondansetron.'),
 (12, True, 'AFib is first: four out of four symptoms matched.'),
 (12, False, 'AFib is first: 3 of 4 selected symptoms matched.'),
 (13, True, 'UTI (urinary tract infection).'),
 (13, False, 'Autism.'),
 (14, True, 'Lucia Ferreira reviewed five articles.'),
 (14, False, 'Lucia Ferreira reviewed 6 articles; reference 5.'),
 (15, True, 'The profile shows Jordan Rivera.'),
 (18, True, 'Four saved articles.'),
 (18, True, 'Saved articles: four.'),
 (18, False, 'There are 5 saved articles; reference number 4.'),
 (19, True, 'Atorvastatin has more conditions. Only its list includes Chronic Kidney Disease and Stroke.'),
 (19, True, 'Atorvastatin: 4; rosuvastatin: 2. The additional conditions are Chronic Kidney Disease and Stroke.'),
 (19, True, 'Atorvastatin, not rosuvastatin, has more linked conditions: Chronic Kidney Disease and Stroke are unique to it.'),
 (19, False, 'Rosuvastatin has more conditions than atorvastatin; its extras are Chronic Kidney Disease and Stroke.'),
 (19, False, 'Atorvastatin does not have more conditions. Chronic Kidney Disease and Stroke.'),
 (19, False, 'Atorvastatin has more conditions. Rosuvastatin alone lists Chronic Kidney Disease and Stroke.'),
]

class AnswerTests(unittest.TestCase):
    def test_answers(self):
        for task, expected, answer in CASES:
            with self.subTest(task=task, expected=expected, answer=answer):
                self.assertEqual(answer_ok(task, answer, FIXTURE), expected)

if __name__ == '__main__':
    unittest.main()
