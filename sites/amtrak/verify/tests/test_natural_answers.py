"""Independent prose/bullet/table equivalents and adversarial claim controls."""

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path[:0] = [
    str(Path(__file__).resolve().parent),
    str(Path(__file__).resolve().parents[1]),
]
import test_verify_matrix as matrix
from natural_answer import checks
from natural_responses import response

POSITIVE = {
    0: [
        "Acela Express train 2151 is the fastest direct train. It takes 170 minutes in total.",
        "- Route: Acela Express\n- Train: 2151\n- Total: 2 hours 50 minutes",
    ],
    1: [
        "Starting at USD 26.88, the cheapest itinerary is Northeast Regional.",
        "Northeast Regional — $26.88.",
    ],
    2: [
        "Business: 124.83 dollars per person for the return journey.",
        "The per-traveler Business fare is $124.83; Value is $90.86.",
    ],
    3: ["For the whole journey, Value costs USD 169.65 per traveler."],
    4: ["The least expensive room upgrade is a Roomette, adding 316 dollars."],
    5: [
        "ALJDAM leaves Chicago on April 20, 2026. Originally paid: $106.06; current Flexible quote: $108.56 including fees. That is $2.50 more."
    ],
    6: [
        "Acela Express, April 20, 2026. Existing booking: $99.74. Today's Business quote including fees: $102.24. Difference: $2.50."
    ],
    7: [
        "Alice has four thousand seven hundred eighty-six rewards points; 2,386 points YTD; 28 status credits. Bob has 4,186 rewards points; 2,386 points YTD; 29 status credits. Alice is 600 points ahead of Bob.",
        "| Account | Balance | Points YTD | Status credits |\n|---|---|---|---|\n| Alice | 4,786 | 2,386 | 28 |\n| Bob | 4,186 | 2,386 | 29 |\nThe balance difference is 600 points.",
    ],
    8: ["SEA is now the saved preferred station."],
    9: [
        "Stops: VAN → SEA → PDX → EUG. Checked baggage: VAN no; SEA yes; PDX yes; EUG no."
    ],
    10: [
        "Before reserving a sleeping room on a tight timetable, check the fares screen. Roomette is cheapest, adding $316.",
        "Consult the pricing page prior to booking a sleeper if you are short on time. A Roomette adds $316.00.",
    ],
    11: [
        "Westbound boarding uses track 3. California Zephyr train #5 leaves at 7:08 AM. Denver supports checked baggage."
    ],
    12: ["California Zephyr offers a Flexible fare of 96.56 dollars."],
    13: [
        "Capitol Corridor:\n| Fare | Price |\n|---|---|\n| Saver | $37.22 |\n| Flexible | $49.87 |\nUpgrade cost: $12.65.",
        "Capitol Corridor: Saver and Flexible cost $37.22 and $49.87 respectively. The difference is $12.65.",
        "Capitol Corridor: $37.22 for Saver versus $49.87 for Flexible. That is $12.65 extra per person.",
    ],
    14: [
        "Unlike Anaheim (ANA), Santa Barbara (SBA) supports checked baggage. Stops: SLO → SBA → LAX → ANA → SAN. Baggage cutoff: 45 minutes before staffed long-distance departures."
    ],
    15: [
        "For long-distance trains at staffed stations, checked bags close 45 minutes before departure. Train 5 leaves at 2:00 PM, so the baggage deadline is 1:15 PM."
    ],
    16: [
        'The article is "Refund language used in the mirror", under Refunds. Saver is $57.11 and gives credit only after the simulated cancellation period. Flexible is $76.53 and refunds to the original demo payment method. Upgrading costs $19.42.'
    ],
}

NEGATIVE = [
    (0, "onboard-not-total", "Acela Express train 2151 takes 166 minutes in total."),
    (
        0,
        "wrong-total-reference",
        "Acela Express train 2151 takes 480 minutes. Another train takes 170 minutes.",
    ),
    (1, "price-reference", "Northeast Regional costs $999.00. Reference number 26.88."),
    (1, "denied-price", "Northeast Regional does not cost $26.88."),
    (2, "business-wrong", "Business costs $999.00. Reference 124.83."),
    (2, "fare-swap", "Business costs $90.86; Value costs $124.83."),
    (3, "value-wrong", "Value costs $147.51; reference 169.65."),
    (4, "wrong-room", "Bedroom adds $316.00."),
    (
        5,
        "reversed-prices",
        "Booking ALJDAM leaves CHI on April 20, 2026. Recorded total $108.56; current Flexible $106.06; increase $2.50.",
    ),
    (
        6,
        "wrong-increase",
        "Acela Express on April 20, 2026. Recorded $99.74; current Business $102.24; increase $9.50.",
    ),
    (
        9,
        "extra-stop",
        "Stops: VAN, SEA, CHI, PDX, EUG. VAN carry-on only; SEA has checked baggage; PDX has checked baggage; EUG carry-on only.",
    ),
    (
        10,
        "keyword-only",
        "Ignore the fare page and reserve any sleeper immediately. Roomette adds $316.",
    ),
    (
        10,
        "after-booking",
        "Check the fare page after booking a sleeper on a tight schedule. Roomette costs $316.",
    ),
    (
        11,
        "wrong-track-reference",
        "Use track 2 for Denver. Track 3 is for an unrelated train. Train 5 departs 07:08. DEN has checked baggage.",
    ),
    (
        11,
        "wrong-train",
        "Denver track 3. Train 6 departs 07:08. Train 5 is an unrelated reference. DEN has checked baggage.",
    ),
    (
        13,
        "swapped-fares",
        "Capitol Corridor: Saver $49.87; Flexible $37.22; upgrade $12.65.",
    ),
    (
        13,
        "wrong-units",
        "Capitol Corridor: Saver 37.22 minutes; Flexible 49.87 minutes; upgrade 12.65 minutes.",
    ),
    (
        13,
        "wrong-currency",
        "Capitol Corridor: Saver €37.22; Flexible €49.87; upgrade €12.65.",
    ),
    (
        14,
        "wrong-property",
        "Santa Barbara (SBA) has free Wi-Fi. Neither ANA nor SBA offers checked baggage. Stops SLO, SBA, LAX, ANA, SAN. Baggage cutoff 45 minutes.",
    ),
    (
        15,
        "wrong-cutoff",
        "Checked baggage closes 5 minutes before long-distance departures at staffed stations. Reference 45. Train 5 departs 14:00; deadline 13:15.",
    ),
    (
        15,
        "swapped-times",
        "Checked baggage cutoff is 45 minutes before long-distance departures at staffed stations. Train 5 departs 13:15; baggage deadline 14:00.",
    ),
    (
        16,
        "refund-swap",
        "Refund language used in the mirror, category Refunds. Saver $57.11, refundable to the local payment placeholder. Flexible $76.53, credit only after a cancellation window. Upgrade $19.42.",
    ),
]


class NaturalAnswers(unittest.TestCase):
    def test_explicit_after_observations_preserve_url_pairing(self):
        from contract import observed
        trajectory = {'steps': [{
            'url': 'http://localhost:40039/',
            'url_after': 'http://localhost:40039/routes',
            'observed_text': 'Home only',
            'observed_text_before': 'Home only',
            'observed_text_after': 'California Zephyr',
        }]}
        self.assertTrue(observed(trajectory, '/routes', 'California Zephyr'))
        self.assertFalse(observed(trajectory, '/routes', 'Home only'))
        self.assertTrue(observed(trajectory, '/', 'Home only'))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.expected = {}
        helper = matrix.Contracts()
        for n in range(18):
            root = Path(self.temp.name) / str(n)
            root.mkdir()
            initial, after, tr = helper.build(n, root)
            self.expected[n] = json.loads(tr["final_answer"])

    def test_all_normal_responses(self):
        for n, a in self.expected.items():
            with self.subTest(task=n):
                verdict = checks(n, response(n, a), a)
                self.assertTrue(all(verdict.values()), verdict)

    def test_independent_equivalents(self):
        for n, answers in POSITIVE.items():
            for answer in answers:
                with self.subTest(task=n, answer=answer):
                    verdict = checks(n, answer, self.expected[n])
                    self.assertTrue(all(verdict.values()), verdict)

    def test_wrong_claims(self):
        for n, label, answer in NEGATIVE:
            with self.subTest(task=n, control=label):
                verdict = checks(n, answer, self.expected[n])
                self.assertFalse(all(verdict.values()), verdict)

    def test_empty_and_contradictory_answers(self):
        for n, a in self.expected.items():
            with self.subTest(task=n, kind="empty"):
                self.assertFalse(all(checks(n, "", a).values()))
        a = self.expected[11]
        self.assertFalse(
            all(checks(11, response(11, a) + " Denver uses track 9.", a).values())
        )
        a = self.expected[14]
        self.assertFalse(
            all(
                checks(
                    14, response(14, a) + " SBA does not offer checked baggage.", a
                ).values()
            )
        )

    def test_wrong_nested_entities_and_dates(self):
        for n in (7, 9, 14):
            a = self.expected[n]
            bad = copy.deepcopy(a)
            if n == 7:
                bad["alice"], bad["bob"] = bad["bob"], bad["alice"]
            else:
                code = next(iter(bad["checked_baggage"]))
                bad["checked_baggage"][code] = not bad["checked_baggage"][code]
            with self.subTest(task=n):
                self.assertFalse(all(checks(n, response(n, bad), a).values()))
        for n in (5, 6):
            a = self.expected[n]
            answer = (
                response(n, a).replace("2026-04-20", "2026-04-21")
                + " Reference date: 2026-04-20."
            )
            with self.subTest(task=n):
                self.assertFalse(all(checks(n, answer, a).values()))
        a = self.expected[7]
        answer = response(7, a).replace("4,786 points", "1 point") + " Reference 4786."
        self.assertFalse(all(checks(7, answer, a).values()))

    def test_natural_answers_do_not_bypass_evidence_or_state(self):
        helper = matrix.Contracts()
        for n in range(18):
            with self.subTest(task=n), tempfile.TemporaryDirectory() as td:
                initial, after, tr = helper.build(n, Path(td))
                tr["final_answer"] = response(n, json.loads(tr["final_answer"]))
                self.assertTrue(helper.grade(n, initial, after, tr).passed)
                for step in tr["steps"]:
                    step["observed_text"] = ""
                self.assertFalse(helper.grade(n, initial, after, tr).passed)


if __name__ == "__main__":
    unittest.main()
