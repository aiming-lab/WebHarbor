"""Routing, filter semantics and fixture invariants on an isolated database."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]


class GuidanceRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.runtime = Path(cls.tmp.name)/'site'
        shutil.copytree(SOURCE,cls.runtime,ignore=shutil.ignore_patterns('instance','instance_seed','__pycache__','static','verify'))
        shutil.copytree(SOURCE/'instance_seed',cls.runtime/'instance')
        cls.before=hashlib.sha256((cls.runtime/'instance/gov_uk.db').read_bytes()).hexdigest()
        program = r'''
import json
from app import app
with app.test_client() as client:
    routes = ['/search?q=passport&type=guidance', '/search?type=news&order=updated&page=2',
              '/search?type=news&department=hm-treasury&order=updated',
              '/search?q=VAT', '/search?page=0', '/search?page=abc', '/search?page=999',
              '/search?type=bogus', '/search?department=bogus', '/search?order=bogus',
              '/guidance/the-new-state-pension/what-youll-get',
              '/guidance/the-new-state-pension/unknown',
              '/guidance/vat-rates/rates',
              '/government/organisations/hm-treasury/about']
    print(json.dumps({r:{'status':client.get(r).status_code,'body':client.get(r).text} for r in routes}))
'''
        cls.results=json.loads(subprocess.check_output([sys.executable,'-c',program],cwd=cls.runtime))

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_guidance_filter_excludes_services(self):
        body=self.results['/search?q=passport&type=guidance']['body']
        self.assertIn('href="/guidance/passport-photos"',body)
        self.assertNotIn('href="/guidance/apply-for-or-renew-an-adult-passport"',body)

    def test_organisation_filter_and_sort(self):
        body=self.results['/search?type=news&department=hm-treasury&order=updated']['body']
        self.assertLess(body.index('href="/government/news/spring-statement'),body.index('href="/government/news/autumn-budget'))
        self.assertNotIn('href="/government/news/self-assessment',body)

    def test_pagination_retains_filters(self):
        result=self.results['/search?type=news&order=updated&page=2']
        self.assertEqual(result['status'],200)
        self.assertIn('type=news&amp;department=&amp;order=updated&amp;page=1',result['body'])
        self.assertNotIn('href="/government/news/spring-statement',result['body'])

    def test_invalid_routes_are_not_silent_fallbacks(self):
        for route,expected in [('/search?page=0',400),('/search?page=abc',400),('/search?page=999',404),
             ('/search?type=bogus',400),('/search?department=bogus',400),('/search?order=bogus',400),
             ('/guidance/the-new-state-pension/unknown',404),('/guidance/vat-rates/rates',404)]:
            with self.subTest(route=route):self.assertEqual(self.results[route]['status'],expected)

    def test_guide_parts_and_seed_are_stable(self):
        body=self.results['/guidance/the-new-state-pension/what-youll-get']['body']
        self.assertIn('£221.20',body)
        self.assertIn('aria-current="page"',body)
        self.assertIn('/guidance/the-new-state-pension/how-to-claim',body)
        self.assertNotIn('Your first payment should arrive',body)
        self.assertEqual(self.before,hashlib.sha256((self.runtime/'instance/gov_uk.db').read_bytes()).hexdigest())

    def test_whole_word_search(self):
        self.assertNotIn('private-renting',self.results['/search?q=VAT']['body'])
