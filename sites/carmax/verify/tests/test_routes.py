"""Isolated Flask route contracts; never import against the developer's live DB."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = Path(__file__).parents[2]
        seed = cls.site/'instance_seed/carmax.db'
        if not seed.exists():
            raise unittest.SkipTest('Fetch the pinned CarMax seed before route tests')
        cls.sandbox = tempfile.TemporaryDirectory()
        cls.root = Path(cls.sandbox.name)
        for name in ['app.py','seed_data.py']:
            shutil.copy2(cls.site/name,cls.root/name)
        shutil.copytree(cls.site/'templates',cls.root/'templates')
        (cls.root/'instance').mkdir()
        shutil.copy2(seed,cls.root/'instance/carmax.db')
        cls.seed_hash = hashlib.sha256(seed.read_bytes()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.sandbox.cleanup()

    def request(self, path):
        script = 'import app,json; r=app.app.test_client().get(' + repr(path) + '); print(json.dumps([r.status_code,r.get_data(as_text=True)]))'
        result = subprocess.run([sys.executable,'-c',script],cwd=self.root,capture_output=True,text=True,check=True)
        return json.loads(result.stdout)

    def test_value_browse_links(self):
        for path, link in [('/value','/value/honda'),('/value/honda','/value/honda/accord'),
                           ('/value/honda/accord','/value/honda/accord/2020')]:
            status, body = self.request(path)
            self.assertEqual(status,200)
            self.assertIn('href="'+link+'"',body)

    def test_invalid_value_routes(self):
        for path in ['/value/not-a-make','/value/honda/not-a-model','/value/honda/accord/1900']:
            self.assertEqual(self.request(path)[0],404)

    def test_pagination_replaces_page(self):
        from html import unescape
        from urllib.parse import parse_qs, urlsplit
        import re
        status, body = self.request('/cars?sort=price_low&page=2')
        self.assertEqual(status,200)
        links = re.findall(r'href="([^"]+)"',body)
        pages = [parse_qs(urlsplit(unescape(link)).query) for link in links if 'page=' in link]
        self.assertTrue(pages)
        self.assertTrue(all(len(q['page']) == 1 and q['sort'] == ['price_low'] for q in pages))
        self.assertTrue(any(q['page'] == ['3'] for q in pages))

    def test_scoped_pagination_handles_redundant_make(self):
        # Synthetic count forces pagination on a scope with exactly one page in
        # the seed. No catalog rows or browser task evidence are modified.
        script = ('import app,json; original=app.search_vehicles; '
                  'app.search_vehicles=lambda *a,**kw: (original(*a,**kw)[0],49); '
                  'r=app.app.test_client().get("/cars/toyota?make=toyota&page=1"); '
                  'print(json.dumps([r.status_code,r.get_data(as_text=True)]))')
        result = subprocess.run([sys.executable,'-c',script],cwd=self.root,capture_output=True,text=True,check=True)
        status, body = json.loads(result.stdout)
        self.assertEqual(status,200)
        self.assertIn('class="pagination"', body)

    def test_read_only_startup_keeps_seed_bytes(self):
        self.request('/value/honda/accord/2020')
        self.assertEqual(hashlib.sha256((self.root/'instance/carmax.db').read_bytes()).hexdigest(),self.seed_hash)


if __name__ == '__main__':
    unittest.main()
