"""Deterministic SEC task contract; see verify/README.md."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_lib

SPEC = {'task_id': 'SEC.gov--12',
 'paths': ['/newsroom',
           '/newsroom/press-releases/2026-98-sec-charges-meyer-global',
           '/newsroom/press-releases\\?q=Zoe\\+Financial',
           '/newsroom/press-releases/2026-94-sec-charges-registered-investment-adviser',
           '/subscribe'],
 'claims': [['latest title', 'sec charges meyer global management and its ceo'],
            ['latest number', '2026-98'],
            ['latest date', 'sept\\.?\\s*30,?\\s*2026'],
            ['pre-IPO company', 'spacex'],
            ['Zoe charge',
             'failing to fully and fairly disclose material facts concerning conflicts of '
             'interest'],
            ['Zoe number', '2026-94'],
            ['Zoe date', 'sept\\.?\\s*28,?\\s*2026'],
            ['subscription confirmation', 'news\\.fan@example\\.com[^.]*subscribed']],
 'forbidden': [['wrong Zoe number', '\\b2026-9[0-3579]\\b'],
               ['wrong latest number', '\\b2026-9[79]\\b(?!.{0,80}meyer global management)']],
 'state': {'email_subscriptions': {'added': [{'email': 'news.fan@example.com',
                                              'topics': 'press releases',
                                              'submitted_at': '2026-09-30'}]}}}

if __name__ == '__main__':
    raise SystemExit(verify_lib.main(SPEC['task_id'], SPEC))
