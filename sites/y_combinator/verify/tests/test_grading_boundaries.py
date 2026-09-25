"""Grading examples whose expectations follow task facts and allowed changes."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify_lib as v


class AnswerBoundaries(unittest.TestCase):
    def answer(self, task, text, facts):
        judge = v.Checks(task)
        v.answer_checks(judge, {'final_answer': text}, facts)
        return judge.result()['pass']

    def test_denied_company_facts_fail(self):
        facts = {'company': {'team_size': 641, 'year_founded': 2009, 'location': 'Boston'}}
        self.assertFalse(self.answer(0, 'Not 641 staff; not founded in 2009; not located in Boston.', facts))
        self.assertTrue(self.answer(0, '641 staff; founded in 2009; located in Boston.', facts))

    def test_negation_scope_does_not_cross_sentences(self):
        self.assertTrue(v.affirmative_phrase('Not the other company. Panorama Education is larger.', 'Panorama Education'))
        self.assertFalse(v.affirmative_phrase('Panorama Education is not the larger company.', 'Panorama Education'))

    def test_publication_date_requires_the_day_and_accepts_date_formats(self):
        facts = {'article': {'series': 'AI Startup School', 'view_count': 2535910,
                             'created_at': '2025-06-19T01:05:19.000Z'}}
        for date in ('June 1, 2025', 'June 2025', '2025-06-20'):
            self.assertFalse(self.answer(16, f'AI Startup School; 2,535,910 views; {date}.', facts))
        for date in ('June 19, 2025', '19 June 2025', 'Jun 19, 2025', 'Jun. 19, 2025', '2025-06-19'):
            self.assertTrue(self.answer(16, f'AI Startup School; 2,535,910 views; {date}.', facts))

    def test_founder_task_requires_company_page_facts(self):
        facts = {'company': {'name': 'Rigetti Computing', 'team_size': 51,
                             'industry': 'Industrials', 'location': 'San Francisco'}}
        self.assertFalse(self.answer(
            4, 'Rigetti Computing, Summer 2014; Chad Rigetti is Founder/CEO.', facts))
        self.assertTrue(self.answer(
            4, 'Rigetti Computing has 51 people in Industrials and is in San Francisco.', facts))

    def test_government_task_does_not_require_the_visible_result_count(self):
        facts = {'company': {'name': 'Verdant', 'batch': 'Summer 2026', 'team_size': 2}}
        self.assertTrue(self.answer(17, 'Verdant — Summer 2026, team size 2.', facts))

    def test_people_task_requires_profile_only_facts(self):
        facts = {'person': {'name': 'Jessica Livingston', 'title': 'Founder, Retired',
                            'group': 'Founders'},
                 'book': 'Founders at Work', 'previous_role': 'VP of marketing',
                 'previous_employer': 'Adams Harkness'}
        self.assertFalse(self.answer(
            13, 'Jessica Livingston — Founder, Retired, in the Founders section.', facts))
        self.assertTrue(self.answer(
            13, 'Jessica Livingston — Founder, Retired, in Founders. She wrote Founders at Work '
                'and was VP of marketing at Adams Harkness.', facts))

    def test_comparison_reversal_fails(self):
        a = {'name': 'Codecademy', 'slug': 'codecademy', 'team_size': 225, 'batch': 'Summer 2011'}
        b = {'name': 'Panorama Education', 'slug': 'panorama-education', 'team_size': 350, 'batch': 'Summer 2013'}
        facts = {'companies': [a, b], 'larger': b}
        details = 'Codecademy: 225 staff, Summer 2011. Panorama Education: 350 staff, Summer 2013.'
        self.assertFalse(self.answer(14, 'Codecademy has the larger team. ' + details, facts))
        self.assertFalse(self.answer(14, 'The larger team is at Codecademy. ' + details, facts))
        self.assertTrue(self.answer(14, 'Panorama Education has the larger team. ' + details, facts))
        self.assertTrue(self.answer(14, 'The larger team is at Panorama Education. ' + details, facts))
        self.assertTrue(self.answer(14, 'Compared with Codecademy, Panorama Education has a larger team. ' + details, facts))
        self.assertTrue(self.answer(14, 'Codecademy has a smaller team than Panorama Education. ' + details, facts))
        self.assertTrue(self.answer(14, details, facts))
        self.assertFalse(self.answer(14, 'Panorama Education has a smaller team than Codecademy. ' + details, facts))

    def test_regional_exclusion_is_a_valid_explanation(self):
        facts = {'document': {'filename': 'Postmoney Safe - Valuation Cap Only - FINAL.docx'}}
        self.assertTrue(self.answer(12, facts['document']['filename'] +
                                   '. I excluded the Canada, Cayman and Singapore variants.', facts))
        self.assertFalse(self.answer(12, 'The Canada variant is my answer.', facts))


class VoteBoundaries(unittest.TestCase):
    def setUp(self):
        self.launch = {'id': 3, 'vote_count': 10, 'tagline': 'Original'}
        self.before = {'user': {1: {'id': 1, 'email': 'bob.m@test.com'}},
                       'launch': {3: self.launch}, 'launch_vote': {}}
        self.after = deepcopy(self.before)
        self.after['launch'][3]['vote_count'] = 11
        self.after['launch_vote'][1] = {'id': 1, 'user_id': 1, 'launch_id': 3}
        self.facts = {'launch': self.launch, 'email': 'bob.m@test.com'}
        self.trajectory = {'start_url': 'http://localhost:40026/',
                           'steps': [{'url': 'http://localhost:40026/login'}]}

    def passes(self):
        judge = v.Checks(9)
        v.state_checks(judge, self.trajectory, self.before, self.after, self.facts)
        return judge.result()['pass']

    def test_legitimate_vote_passes(self):
        self.assertTrue(self.passes())

    def test_other_target_fields_cannot_change(self):
        self.after['launch'][3]['tagline'] = 'Extra change'
        self.assertFalse(self.passes())

    def test_extra_launch_cannot_be_added(self):
        self.after['launch'][4] = {'id': 4, 'vote_count': 0, 'tagline': 'Extra row'}
        self.assertFalse(self.passes())

    def test_preexisting_vote_cannot_be_reassigned(self):
        self.before['launch_vote'][2] = {'id': 2, 'user_id': 2, 'launch_id': 3}
        self.after['launch_vote'][2] = {'id': 2, 'user_id': 3, 'launch_id': 3}
        self.assertFalse(self.passes())


if __name__ == '__main__':
    unittest.main()
