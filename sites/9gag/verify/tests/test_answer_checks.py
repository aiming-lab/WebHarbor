"""Answer-only controls; UI/DB gates remain covered by per-task verifier tests."""
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from answer_checks import check

KEYS = {0: ('width','material'), 1: ('month','days'), 2: ('power','protection'),
        3: ('frequency','feature'), 4: ('color','day','time'), 5: ('distance','color'),
        6: ('attempts','hours'), 7: ('switches','case'), 8: ('platform',), 9: ('name',)}

POSITIVE = [
 (0, 'Four point two metres wide; the desk is oak that was salvaged.'),
 (4, 'Blue, restocked Thursday at six in the morning.'),
 (5, 'Kilometer thirty eight, orange flags.'),
 (6, 'Attempts: 3. Shaping time: 14h.'),
 (7, 'Tactile, quiet switches and an acrylic case.'),
 (8, 'Platform 7.'),
 (0, 'The room is 4.2 metres wide; the desktop is made of salvaged oak.'),
 (0, 'Width: 420 cm. Desk: reclaimed oak.'),
 (1, 'February; eleven days.'),
 (1, 'Miso came to Harbor Paws in February. Learning took 11 days.'),
 (2, 'A 0.12 kW panel, with the controller in a waterproof lunchbox.'),
 (2, 'Panel: 120W. Protection: a lunch-box.'),
 (3, 'The evenly spaced railings create the note, at 0.44 kHz.'),
 (4, 'Blue; replenished on Thursdays at 06:00.'),
 (4, 'The blue cabinet is restocked every Thursday at 6 a.m. by local volunteers.'),
 (5, 'Kilometre 38; orange flags.'),
 (5, 'They met at 38 km carrying handmade orange flags.'),
 (6, 'It took a trio of attempts and roughly fourteen hours to shape.'),
 (6, '3 tries and 840 minutes of shaping.'),
 (6, 'Attempts: three. Shaping time: about 14 hours.'),
 (7, 'Quiet tactile switches in a hand-polished acrylic case.'),
 (7, 'Tactile switches that are silent; the casing is Perspex.'),
 (8, 'Platform seven.'), (8, '7'),
 (9, 'The fox has the most points, and its name is Copper.'),
 (9, 'Copper'),
 (9, 'The garden fox, Copper, wins. The cat does not have the most points.'),
]
NEGATIVE = [
 (7, 'It has linear switches. Reference models have silent tactile switches. The case is acrylic.'),
 (9, 'The cat has more points than the fox Copper.'),
 (0, 'The room is 4.2 centimeters wide and the desk is reclaimed oak.'),
 (0, 'The room is 4.2 meters wide; its desk is walnut and its shelf is reclaimed oak.'),
 (0, 'The room is not 4.2 metres wide. Its desk is reclaimed oak.'),
 (1, 'Miso arrived in February and learned it in 11 months.'),
 (1, 'Miso arrived in March and learned it in 11 days. The shelter opened in February.'),
 (2, 'The panel supplies 120 kilowatts and a waterproof lunch box protects the controller.'),
 (2, 'The panel is 200 watts. Reference: 120 watts. The controller is in a lunchbox.'),
 (2, 'The panel is 120 W; a dry bag protects the controller and a lunchbox holds the food.'),
 (3, 'The railings resonate at 440 kilohertz.'),
 (3, 'The note is 440 Hz, produced by cables; the railings are only decoration.'),
 (4, 'The blue cabinet is restocked every Friday at 7 a.m. Volunteers meet Thursday at 6 a.m.'),
 (4, 'The cabinet is red and the books are blue. Restocked every Thursday at 6 am.'),
 (4, 'Blue; Thursday at 6 pm.'),
 (5, 'They met at mile 38 with orange flags.'),
 (5, 'At kilometer 38, their flags were blue and their shirts were orange.'),
 (6, 'It took fourteen attempts and about three hours to shape.'),
 (6, 'Three attempts; four hours. The post got fourteen likes.'),
 (6, 'Three attempts and fourteen days.'),
 (7, 'Clicky switches and an acrylic case.'),
 (7, 'Silent tactile switches, an aluminium case and acrylic keycaps.'),
 (8, 'The commuters sang at platform three; seven musicians performed.'),
 (8, 'Platform 7 is wrong; they sang at platform 3.'),
 (9, 'The rescue-cat post has the most points; the garden fox is named Copper.'),
 (9, 'Winner: the cat. The fox is Copper.'),
 (9, 'The fox Copper does not have the most points.'),
]

class AnswerSemanticsTests(unittest.TestCase):
    def test_correct_equivalents(self):
        for n,answer in POSITIVE:
            with self.subTest(task=n,answer=answer):
                self.assertTrue(all(check(n,key,answer) for key in KEYS[n]))

    def test_wrong_facts_and_contradictions(self):
        for n,answer in NEGATIVE:
            with self.subTest(task=n,answer=answer):
                self.assertFalse(all(check(n,key,answer) for key in KEYS[n]))

if __name__ == '__main__':
    unittest.main()
