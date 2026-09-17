"""Audit-derived synthetic answer controls, with independent copied DB fixtures."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cases import CASES
from _support import State, VerifierTestCase, step

class ReviewRegressions(VerifierTestCase):
    def test_answer_controls(self):
        for spec in json.loads(Path(__file__).with_name('answer_controls.json').read_text()):
            with self.subTest(task=spec['task'], name=spec['name']):
                self.N=spec['task']; case=CASES[self.N]; after=State()
                if case.get('after'): case['after'](after)
                verdict=self.verdict(case['steps'],spec['answer'],after=after)
                self.assertEqual(verdict['pass'], spec['expected'], verdict['evidence'])

    def test_search_required_for_phoenix(self):
        self.N=0
        self.assertFailsOn(self.verdict([step('/'),step('/weather/phoenix-az','done')],CASES[0]['answer']), 'searched_for_phoenix-az')

    def test_radar_must_precede_return_to_weather(self):
        self.N=11
        steps=CASES[11]['steps'][:-1]
        self.assertFailsOn(self.verdict(steps,CASES[11]['answer']), 'radar_then_current_weather')
