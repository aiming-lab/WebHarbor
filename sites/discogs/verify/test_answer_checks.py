"""Natural-answer regression matrix; no prescribed answer format for agents."""
import unittest
from answer_checks import check_answer

GOOD = {
    0: "The 1966 edition prints durations. Its catalog numbers are 242 and RS 9242; Well, You Needn't is 11:24.",
    1: "The 1986 CD edition, catalog CP32-5244, contains Bellarosa with a displayed duration of 4:15.",
    2: "The Japan 2007 edition has 7 numbered tracks; its catalog number is UCCO-9038 and Joe Tarantino is credited for digital remastering.",
    3: "Release 9732909 lists the extra Impuesto de lujo entry Num. 6649. The other edition is release 8837214. Both editions share Deposito Legal B. 9417-1978.",
    4: "Live God: bass player is Colin Greenwood; the last track on side D is As The Waters Cover The Sea. Live From KCRW: bass player is Martyn P. Casey; the last track on side D is Jack The Ripper, with a duration of 6:11. Live God shows no duration for its closer.",
    5: "Kelly Blue by Wynton Kelly is sold by kosmische for 8.27 USD; the label catalog numbers are SMJ-6114 and SRS-6059. Legacy US catalog numbers: 12-298 and RLP 12-298.",
    6: "The third release is Lonely Avenue by The Boulevard Of Broken Dreams Orchestra, from Netherlands, catalog 30-90342, with 13 tracks. The fourth is Jeff Beck by Jeff Beck, from Italy, catalog IGDA 1063/64, with 10 tracks. Lonely Avenue has 3 more tracks.",
}
ALTERNATIVES = {
    0: ["It is the 1966 release. The two catalogue identifiers are RS 9242 and 242, and Well, You Needn't runs 11 minutes 24 seconds (11:24).",
        "1961: durations are blank.\n1966: durations are listed. Catalogs: 242 / RS 9242. Well, You Needn't: 11 min 24 sec.",
        "| Edition | Track durations | Catalog numbers | Well, You Needn't |\n|---|---|---|---|\n| 1966 | listed | 242 and RS 9242 | 11:24 |"],
    1: ["Bellarosa is absent from the 1994 edition. The 1986 Japanese CD contains Bellarosa, catalogue CP32-5244, duration 4 minutes 15 seconds.",
        "The 1986 Japanese CD edition contains Bellarosa, with catalog number CP32-5244 and a displayed duration of 4:15. Bellarosa is absent from the 1994 Japanese edition."],
    2: ["Japan's 2007 UCCO-9038 version is the one with seven tracks; digital remastering is credited to Joe Tarantino."],
    3: ["The extra Impuesto de lujo line, Num. 6649, is printed on release 9732909. Release 8837214 stops at two identifiers. Both carry Deposito Legal B. 9417-1978."],
    4: ["Live From KCRW: Martyn P. Casey is credited on bass; the final side-D track is Jack The Ripper. Duration: 6 minutes 11 seconds.\nLive God: Colin Greenwood plays bass; the final side-D track is As The Waters Cover The Sea. Its duration is unlisted.",
        "| Release | Bass player | Last track on side D | Duration |\n|---|---|---|---|\n| Live God | Colin Greenwood | As The Waters Cover The Sea | not listed |\n| Live From KCRW | Martyn P. Casey | Jack The Ripper | 6:11 |"],
    5: ["At US$8.27, kosmische's Kelly Blue by Wynton Kelly was cheapest. Label catalogues: SRS-6059 plus SMJ-6114. Legacy US catalogues: RLP 12-298 and 12-298.",
        "Title: Kelly Blue; artist: Wynton Kelly; seller: kosmische; price: USD 8.27. Label catalogs: SMJ-6114 and SRS-6059. Legacy US catalog numbers: 12-298 / RLP 12-298."],
    6: ["Lonely Avenue by The Boulevard Of Broken Dreams Orchestra: Netherlands; catalog 30-90342.\nJeff Beck by Jeff Beck: Italy; catalog IGDA 1063/64.\nLonely Avenue has more tracks, by three.",
        "| Title | Artist | Country | Catalog number | Track count |\n|---|---|---|---|---|\n| Lonely Avenue | The Boulevard Of Broken Dreams Orchestra | Netherlands | 30-90342 | 13 |\n| Jeff Beck | Jeff Beck | Italy | IGDA 1063/64 | 10 |\nLonely Avenue has 3 more tracks."],
}
BAD = {
    0: [GOOD[0].replace('1966 edition prints', '1961 edition prints') + ' The 1966 edition leaves them blank.', GOOD[0].replace('is 11:24', 'is not 11:24'), GOOD[0].replace('11:24', '11:25')],
    1: ["The 1994 Japanese CD contains Bellarosa, catalog CP32-5244, duration 4:15. The 1986 edition lacks that song."],
    2: [GOOD[2].replace('7 numbered tracks', '6 numbered tracks')+' Reference number 7.', GOOD[2]+' Digital remastering: Paul Smith.'],
    3: [GOOD[3].replace('9732909','TEMP').replace('8837214','9732909').replace('TEMP','8837214')],
    4: [GOOD[4].replace('Colin Greenwood','TEMP').replace('As The Waters Cover The Sea','Colin Greenwood').replace('TEMP','As The Waters Cover The Sea'), GOOD[4]+' Live God: bass player is Paul McCartney; the last track on side D is Hey Jude.', GOOD[4].replace('6:11','6:12'), GOOD[4].replace('Live God shows no duration for its closer.','Live God: duration 6:11.')],
    5: [GOOD[5].replace('8.27 USD','99.99 USD')+' Reference 8.27.', GOOD[5].split(' Legacy')[0], GOOD[5].replace('Kelly Blue by','Blow by Blow by'), GOOD[5].replace('sold by kosmische','sold by another_seller')+' Reference kosmische.'],
    6: [GOOD[6].replace('Jeff Beck by Jeff Beck','Blow by Blow by Jeff Beck'), GOOD[6].replace('3 more','2 more'), GOOD[6].replace('Netherlands','Italy'), GOOD[6].replace('30-90342','IGDA 1063/64')],
}
BAD[0].append(GOOD[0].replace('242 and RS 9242', '999 and WRONG-42') + ' Reference codes 242, RS 9242.')
BAD[1].append(GOOD[1].replace('CP32-5244','WRONG-42') + ' Reference CP32-5244.')
BAD[2].append(GOOD[2].replace('UCCO-9038','WRONG-42') + ' Reference UCCO-9038.')
BAD[5].append(GOOD[5] + ' The price is not USD 8.27.')
BAD[6].append(GOOD[6] + ' Jeff Beck has 3 more tracks.')


class AnswerTests(unittest.TestCase):
    def test_correct_prose_bullets_and_tables(self):
        for task in GOOD:
            for text in [GOOD[task], *ALTERNATIVES.get(task, [])]:
                with self.subTest(task=task, answer=text):
                    checks = check_answer(task, text)
                    self.assertTrue(all(checks.values()), checks)

    def test_incorrect_assertions_fail(self):
        for task, answers in BAD.items():
            for text in answers:
                with self.subTest(task=task, answer=text):
                    checks = check_answer(task, text)
                    self.assertFalse(all(checks.values()), checks)


if __name__ == '__main__':
    unittest.main()
