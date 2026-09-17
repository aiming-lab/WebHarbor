"""Semantic and evidence controls; synthetic fixtures are not browser runs."""
import copy
import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'verify'))
from verify_lib import answer_checks, evaluate, llm_text_match

# Independent expected answers cover all task contracts. Ground truth stays out
# of the agent-facing tasks.jsonl.
ANSWERS = ['The standard Personal Allowance is £12,570 per year. It reduces by £1 for every £2 of adjusted net income above £100,000. At £110,000 the reduction is £5,000, so the remaining allowance is £7,570.', 'The full new State Pension is £221.20 per week for 2024 to 2025. It is normally paid every 4 weeks in arrears. A National Insurance number ending in 42 is paid on Wednesday.', 'For the year ending 5 April 2025, paper filing is due by midnight 31 October 2025; online filing is due by midnight 31 January 2026. Pay the tax by 31 January 2026. Use the 11-character payment reference: your UTR followed by K.', "Adult clothing uses the standard 20% rate; children's car seats use 5%; children's clothes use 0%. Zero-rated sales are taxable at 0%, and a VAT-registered business may normally reclaim input VAT on related costs. Exempt supplies do not charge VAT, and businesses cannot normally reclaim VAT on related costs.", 'For a National Insurance record starting after April 2016, the usual minimum is 10 qualifying years for any new State Pension, and 35 qualifying years are needed for the full amount. The Check your State Pension forecast service shows a personal estimate, when it can be claimed and possible ways to increase it.', 'The initial penalty is £100 even if you owe no tax or paid on time. Once the return is more than 3 months late, an additional £10 per day applies for up to 90 days, a maximum of £900. Late payment has separate interest and penalties.', "The individual's annual Capital Gains Tax allowance for 2024 to 2025 is £3,000. The higher rate on taxable ordinary share gains from 15 November 2024 is 24%, under the rates from 30 October 2024. Tax applies to the gain or profit, not the full sale proceeds.", "HMRC's listed lead minister is Rt Hon James Murray MP, Exchequer Secretary. Before filing, gather employment records such as P60, P45 and P11D benefits information, and savings records showing bank interest, along with dividend information if relevant.", "DWP employs 82,000 people in this mirror's profile. You must claim the new State Pension; it is not automatic. Claiming online needs an invitation code, National Insurance number and bank or building society details, plus dates of any time living or working abroad.", 'HM Treasury was established in 1066 according to the profile. Its latest announcement is Spring Statement update on growth measures, published 28 March 2025. Infrastructure investment is intended to improve connections and support businesses; planning reform is intended to help homes and infrastructure move through the planning system.', "The latest announcement is 'Spring Statement update on growth measures', published by HM Treasury on 28 March 2025. Infrastructure investment aims to improve connections and support businesses. Planning reform aims to help homes and infrastructure move through the planning system.", 'HMRC reported more than 11.5 million Self Assessment returns filed by 31 January. Someone unable to pay should file as soon as possible; filing and payment are separate obligations. The initial late-filing penalty is £100, even with no tax due.', 'HM Passport Office is responsible. Prepare a digital photo and a debit or credit card; a renewal also uses the old passport details and any documents requested. The standard adult online fee is £88.50, compared with £100 for paper by post at 1 April 2025. A digital photo must be at least 600 pixels wide and 750 pixels tall, taken within the last month.', 'In England a Blue Badge costs up to £10 and usually lasts up to 3 years; renewal requires reapplying. Prepare a recent digital photo, proof of identity, proof of address and proof of benefits if received, plus your existing badge details and National Insurance number if you have one. Not every PIP award qualifies: specific qualifying scores and descriptors matter. The council assesses walking difficulties and difficulties during journeys when automatic eligibility does not apply.', 'The Home Office publishes the Skilled Worker visa guidance. The visa can last up to 5 years. The worker needs an approved employer and a certificate of sponsorship with its reference number. Generally required evidence includes a valid passport and proof of English, plus job and sponsor details. Depending on circumstances, evidence of savings, a tuberculosis test, relationship documents or a criminal record certificate may also be needed.', "Use DVSA's practical driving-test booking service. A weekday car test costs £62; a Saturday test costs £75. Prepare the UK driving licence number, theory pass details and debit or credit card; an instructor reference can help check availability. An automatic-to-manual upgrade does not need another theory test.", 'You must register again after moving home in England. A National Insurance number is optional: you can register without one, although other identity evidence may be requested. The paper alternative is to send a completed paper registration form to your electoral registration office. Voting in person separately requires accepted original photo ID; a free Voter Authority Certificate is available if you lack accepted ID.', 'FCDO provides the advice. For France, the passport must be issued less than 10 years before arrival and expire at least 3 months after the planned departure. Eligible short visits are visa-free for up to 90 days in any 180-day period across the Schengen area. A GHIC does not replace travel insurance and does not cover all costs. Subscribe to France email alerts from its advice page and confirm by email; the mirror explains this but does not deliver live emails.', "A 15-year-old meets the usual under 16 age criterion. Eligibility can continue for a child under 20 in approved education or training, but a university degree is advanced education and does not qualify, so the 17-year-old's degree is not an eligible extension. A claim can be backdated for up to 3 months. Claiming for a child under 12 gives National Insurance credits that protect the parent's State Pension.", 'The NHS App milestone is 30 million registered users. It supports booking appointments, ordering repeat prescriptions and viewing health records. Features depend on the GP practice and which services it has enabled, and identity verification can be required. It is not an emergency service.']


class AnswerControls(unittest.TestCase):
    def test_fact_relationships_and_valid_alternatives(self):
        cases = [
            (2, False, ANSWERS[2].replace('paper filing', 'TEMP filing').replace('online filing', 'paper filing').replace('TEMP filing', 'online filing')),
            (5, False, ANSWERS[5].replace('3 months late', '6 months late')),
            (9, True, ANSWERS[9].replace('planning reform is intended to help homes and infrastructure move through the planning system.', 'Skills measures help people take up work in growing sectors.')),
            (9, True, ANSWERS[9].replace('Infrastructure investment is intended to improve connections and support businesses;', 'Skills measures help people take up work in growing sectors;')),
            (12, False, ANSWERS[12].replace('600 pixels wide and 750 pixels tall', '600 by 750')),
            (12, True, ANSWERS[12].replace('£88.50', '£88.5')),
            (12, True, ANSWERS[12].replace('600 pixels wide and 750 pixels tall', '750 pixels tall and 600 pixels wide')),
        ]
        for task, expected, answer in cases:
            with self.subTest(task=task, answer=answer):
                self.assertEqual(all(answer_checks(task, answer).values()), expected, answer_checks(task, answer))

    def test_valid_answers(self):
        for i, answer in enumerate(ANSWERS):
            with self.subTest(task=i):
                self.assertTrue(all(answer_checks(i, answer).values()), answer_checks(i, answer))

    def test_equivalent_number_formats(self):
        equivalents = {0: {'£12,570':'12,570 pounds','£7,570':'7,570 pounds'},
                      1: {'£221.20':'221.20 pounds'},4:{'10 qualifying':'ten qualifying','35 qualifying':'thirty-five qualifying'},
                      8: {'82,000':'82 thousand'},11:{'11.5 million':'11500000'},19:{'30 million':'thirty million'}}
        for task, replacements in equivalents.items():
            answer = ANSWERS[task]
            for before, after in replacements.items():answer=answer.replace(before,after)
            with self.subTest(task=task):self.assertTrue(all(answer_checks(task,answer).values()),answer_checks(task,answer))

    def test_empty_disclaimed_and_wrong_answers(self):
        for task, answer in enumerate(ANSWERS):
            for wrong in ['', 'This answer is incorrect. I reject it. '+answer]:
                with self.subTest(task=task):self.assertFalse(all(answer_checks(task,wrong).values()))
        # Each change corrupts a fact or condition independently, retaining the
        # other correct information to expose partial-answer false accepts.
        changes = [
            (0,'£7,570','£12,570'), (0,'£100,000','£120,000'),
            (1,'Wednesday','Friday'), (1,'every 4 weeks','every 2 weeks'),
            (2,'31 October 2025','31 October 2026'), (2,'UTR followed by K','UTR followed by J'),
            (3,'standard 20%','standard 5%'), (3,'children\'s clothes use 0%','children\'s clothes use 20%'),
            (4,'35 qualifying','30 qualifying'), (5,'£100','£1,000'),(5,'£10 per day','£10 per month'),
            (6,'£3,000','£6,000'),(6,'24%','20%'),(7,'James Murray','Jeremy Hunt'),
            (8,'82,000','182,000'),(8,'invitation code','postcode'),(9,'1066','2001'),
            (10,'28 March 2025','28 March 2026'),(11,'11.5 million','11.5 thousand'),
            (12,'£88.50','£94.50'),(12,'600 pixels wide and 750 pixels tall','600 millimetres wide and 750 millimetres tall'),
            (13,'up to £10','£20'),(14,'up to 5 years','up to 5 months'),
            (15,'Saturday test costs £75','Saturday test costs £62'),
            (16,'National Insurance number is optional','National Insurance number is mandatory'),
            (17,'90 days in any 180-day','180 days in any 180-day'),
            (18,'backdated for up to 3 months','backdated for up to 6 months'),
            (19,'30 million registered users','130 million registered users'),
            (19,'not an emergency service','an emergency service'),
        ]
        for task,before,after in changes:
            self.assertIn(before,ANSWERS[task])
            wrong=ANSWERS[task].replace(before,after)
            with self.subTest(task=task,mutation=before):self.assertFalse(all(answer_checks(task,wrong).values()),answer_checks(task,wrong))


class EvidenceControls(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root/'screenshots').mkdir()
        Image.new('RGB',(320,240),'white').save(self.root/'screenshots/frame.png')
        self.url = 'http://localhost:40016/guidance/income-tax-rates-and-personal-allowances'
        self.t = {'task_id':'GOV.UK--0','start_url':'http://localhost:40016/',
                  'terminated':True,'termination_reason':'agent_done',
                  'final_answer':ANSWERS[0], 'steps':[{'url':self.url,'screenshot_before':'frame.png'}, {'url':self.url+'/income-over-100000','screenshot_before':'frame.png'}]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_agent_before_frame_and_gui_after_frame(self):
        self.assertTrue(evaluate(0,self.t,self.root)['pass'])
        step=self.t['steps'][0]
        step.update(url_after=self.url,screenshot_after='frame.png',screenshot_before='missing.png')
        self.assertTrue(evaluate(0,self.t,self.root)['pass'])

    def test_untrusted_metadata(self):
        variants = [
            {'task_id':'GOV.UK--1'}, {'terminated':False}, {'termination_reason':'max_steps'},
            {'success_self_report':False}, {'steps':[]}, {'start_url':'invalid'},
        ]
        for fields in variants:
            with self.subTest(fields=fields):
                t={**self.t,**fields};self.assertFalse(evaluate(0,t,self.root)['pass'])
        for url in [self.url.replace('localhost','evil.test'), self.url.replace(':40016',':40017'),
                    'http://localhost:40016/?target='+self.url, self.url+'-wrong',
                    self.url.replace('http:','https:'), 'http://localhost:40016@evil.test/'+self.url]:
            t=copy.deepcopy(self.t);t['steps'][0]['url']=url
            with self.subTest(url=url):self.assertFalse(evaluate(0,t,self.root)['pass'])

    def test_screenshots(self):
        for name in ['missing.png','../frame.png','/etc/passwd']:
            t=copy.deepcopy(self.t);t['steps'][0]['screenshot_before']=name
            with self.subTest(name=name):self.assertFalse(evaluate(0,t,self.root)['pass'])
        (self.root/'screenshots/frame.png').write_text('not an image')
        self.assertFalse(evaluate(0,self.t,self.root)['pass'])

    def test_required_parts_and_requested_start(self):
        from urllib.parse import urlsplit
        from verify_lib import navigation_checks
        cases = [
            (12,['/search?q=passport','/guidance/apply-for-or-renew-an-adult-passport','/guidance/passport-photos'],True),
            (12,['/guidance/apply-for-or-renew-an-adult-passport','/guidance/passport-photos','/search?q=passport'],False),
            (18,['/browse/childcare','/guidance/child-benefit-eligibility/eligibility','/guidance/child-benefit-eligibility/claim'],True),
            (18,['/browse/childcare','/guidance/child-benefit-eligibility'],False),
            (6,['/guidance/capital-gains-tax-what-you-pay-it-on-rates-and-allowances/allowances','/guidance/capital-gains-tax-what-you-pay-it-on-rates-and-allowances/rates'],True),
            (6,['/guidance/capital-gains-tax-what-you-pay-it-on-rates-and-allowances'],False),
        ]
        for task,paths,expected in cases:
            seen=[urlsplit('http://localhost:40016'+p) for p in paths]
            with self.subTest(task=task,paths=paths):self.assertEqual(all(navigation_checks(task,seen).values()),expected)


class OptionalEndpoint(unittest.TestCase):
    def test_openai_base_path(self):
        seen=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                seen.append(self.path)
                self.rfile.read(int(self.headers['Content-Length']))
                self.send_response(200);self.end_headers()
                self.wfile.write(json.dumps({'choices':[{'message':{'content':'PASS: matches reference'}}]}).encode())
            def log_message(self,*args):pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever);thread.start()
        try:
            with patch.dict(os.environ,{'OPENAI_API_KEY':'local-stub','OPENAI_BASE_URL':f'http://127.0.0.1:{server.server_port}/v1/','JUDGE_MODEL':'stub'}):
                self.assertTrue(llm_text_match('x','x','q')[0])
            self.assertEqual(seen,['/v1/chat/completions'])
        finally:server.shutdown();thread.join();server.server_close()


if __name__=='__main__':unittest.main()
