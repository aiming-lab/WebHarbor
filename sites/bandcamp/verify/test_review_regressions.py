"""Regressions from independent browser evidence; no network/model calls."""
import unittest
from verify_lib import answer_ok, navigation_ok


class ReviewRegressions(unittest.TestCase):
    def test_natural_equivalents(self):
        cases = {
            0: ['Fifteen US dollars.', 'The cassette costs $15.', 'Cassette: USD 15.00', '$15 for the cassette.', 'The cassette costs 1500 cents.'],
            1: ['The third song is Between Stations.', 'Between Stations is the 3rd song.'],
            6: ['Four minutes and thirty-one seconds.', 'Low Pier runs 271 seconds.', 'Track 4: 4:31.', 'The fourth song lasts 4 minutes 31 seconds.', 'Track 2 is 3:33; track 4 is 4:31.'],
            10: ['The digital edition costs $8.50.', '$8.50'],
            12: ['The signed poster costs twenty-seven dollars.', 'Signed $27; Standard $19.'],
            13: ['The cheapest format is Digital Album at $9.50.', 'Digital is $9.50, vinyl is $25, and CD is $17.50.'],
            17: ['You can choose either Natural or Forest.', 'Both Natural and Forest are available.', 'The two color options are Natural and Forest.'],
        }
        for i, answers in cases.items():
            for answer in answers:
                with self.subTest(task=i, answer=answer):
                    self.assertTrue(answer_ok(i, answer))

    def test_wrong_amounts_entities_units_and_contradictions(self):
        cases = {
            0: ['The cassette costs $150.', 'The cassette costs $150. Reference number 15.', 'The cassette costs 15 euros.', 'The cassette costs $1500.', 'The cassette costs $15.01.', 'The cassette costs 15 cents.', 'The digital edition costs $15.', 'The cassette costs $15; the cassette costs $20.', 'The cassette is not $15.'],
            6: ['Track 4 lasts 9:00; 4:31 is track 2.', 'Track 2 lasts 4:31.', 'Low Pier lasts 271 minutes.', 'Track 4 lasts 4:31 and 9:00.', 'Track 4 is not 4:31.', 'Track 4 is 4:310.', 'Track 4 is 4:99.'],
            10: ['The digital edition costs $85; reference 8.5.', 'The digital edition costs $8.5001.', 'Digital costs $8.50. Digital is not $8.50.'],
            12: ['The signed edition costs $270.', 'The signed edition costs $270; product number 27.', 'Standard costs $27.'],
            13: ['Vinyl is cheapest at $24. Digital is $9.50.', 'The cheapest format is vinyl at $25; digital is $9.50.', 'Digital is $95.', 'Digital is the most expensive at $9.50.'],
            17: ['Natural, Forest and Black.', 'Natural or Black.', 'Maybe Natural and Forest.', 'Natural and Forest are not available.'],
        }
        for i, answers in cases.items():
            for answer in answers:
                with self.subTest(task=i, answer=answer):
                    self.assertFalse(answer_ok(i, answer))

    def test_discover_is_observed_ordered_and_same_origin(self):
        origin = 'http://localhost:44907'
        for i, album in [(1, 'between-stations'), (11, 'elastic-hearts')]:
            def check(paths):
                return navigation_ok(i, {'start_url': origin + '/', 'steps': [{'url': p if p.startswith('http') else origin + p} for p in paths]})
            with self.subTest(task=i):
                self.assertTrue(check(['/discover?scene=tokyo-japan', '/album/' + album]))
                self.assertTrue(check(['/discover?q=Tokyo', '/album/' + album]))
                self.assertFalse(check(['/album/' + album]))
                self.assertFalse(check(['/album/' + album, '/discover?scene=tokyo-japan']))
                self.assertFalse(check(['https://evil.example/discover?genre=ambient', '/album/' + album]))
                self.assertFalse(check(['/discover?genre=ambient&genre=rock', '/album/' + album]))
        self.assertFalse(navigation_ok(1, {'start_url': origin, 'steps': [{'url': origin + '/discover'}, {'url': origin + '/album/between-stations'}]}))


if __name__ == '__main__':
    unittest.main()
