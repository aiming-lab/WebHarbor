import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'verify'))
import research_checks as r

class ResearchChecks(unittest.TestCase):
    def test_camera(self):
        for answer in ['18-55mm and 75-300mm; the two-lens kit costs $100.99 extra.', '18 to 55 mm and 75 to 300 mm. The premium is 100 dollars and 99 cents.']:
            self.assertTrue(r.camera_premium(answer, 100.99), answer)
        for answer in ['18-55mm and 75-300mm; costs $1100.99 extra.', 'Neither 18-55mm nor 75-300mm; premium $100.99.', '18-55mm and 75-300mm; starter bundle costs more by $100.99.', '18-55mm and 75-300mm; premium 100.99 points.']:
            self.assertFalse(r.camera_premium(answer, 100.99), answer)

    def test_rewards(self):
        accounts = {'alice': (1840, 0), 'bob': (2080, 1)}
        good = [
            'Alice has 1,840 points and zero certificates. Bob has 2,080 points and one certificate. Bob has more points by 240 points.',
            'Alice: 1840 points; 0 certificates. Bob: 2080 points; 1 certificate. Alice has fewer points by 240 points.',
            '| Account | Points | Certificates |\n| Alice | 1840 | 0 |\n| Bob | 2080 | 1 |\nBob is higher by 240 points.',
        ]
        for text in good: self.assertTrue(r.reward_comparison(text, accounts, 240), text)
        for text in [good[0].replace('1840','2080').replace('1,840','2,080'), good[0].replace('240 points','1240 points'),good[0].replace('Bob has more','Alice has more'),good[0].replace('Bob has more','Bob does not have more')]:
            self.assertFalse(r.reward_comparison(text, accounts, 240), text)

    def test_orders(self):
        orders = {'BBY-240001': ('pickup','Delivered',935.02), 'BBY-240003': ('delivery','Shipped',1085.95)}
        good = 'BBY-240001: pickup, delivered, total $935.02. BBY-240003: delivery, shipped, total $1085.95. BBY-240003 has the higher total by $150.93.'
        self.assertTrue(r.order_comparison(good,orders,'BBY-240003',150.93))
        for text in [good.replace('935.02','1935.02'),good.replace('pickup, delivered','delivery, shipped'),good.replace('higher total by $150.93','higher total by $1150.93')]:self.assertFalse(r.order_comparison(text,orders,'BBY-240003',150.93),text)

    def test_pickup(self):
        self.assertTrue(r.pickup_plan('Bring order number and photographic identification; ready in 1 hour, aisle D-8.','D-8'))
        for text in ['Bring nothing; no order number or photo ID. Ready today, D-8.', 'Order number and photo ID; ready tomorrow, D-8.', 'Order number and photo ID; ready in 1 hour, D-80.', 'Order number and photo ID; ready in 1 hour or tomorrow, D-8.']:
            self.assertFalse(r.pickup_plan(text,'D-8'),text)

    def test_deals(self):
        expected={'omnibook':(45,400),'victus':(39,575)}
        for text in ['HP OmniBook: 45% off, saves $400. HP Victus: 39% off, saves $575.', 'OmniBook | forty-five percent | four hundred dollars\nVictus | thirty-nine percent | five hundred seventy-five dollars']:
            self.assertTrue(r.deals(text,expected),text)
        for text in ['OmniBook 45% $575; Victus 39% $400','OmniBook 145% $400; Victus 39% $575','Not OmniBook 45% $400; Victus 39% $575']:
            self.assertFalse(r.deals(text,expected),text)
