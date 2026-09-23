"""Exercise the actual Flask form/session flow in an isolated temporary site."""
import importlib.util
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


class LookupSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();root=Path(cls.tmp.name)
        source=Path(__file__).parents[1]
        for name in ['app.py','seed_data.py']:
            shutil.copyfile(source/name,root/name)
        shutil.copytree(source/'templates',root/'templates')
        (root/'instance').mkdir()
        sys.path.insert(0,str(root))
        spec=importlib.util.spec_from_file_location('irs_lookup_test_app',root/'app.py')
        cls.module=importlib.util.module_from_spec(spec)
        sys.modules[spec.name]=cls.module
        spec.loader.exec_module(cls.module)
        cls.app=cls.module.app;cls.app.config['TESTING']=True

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():cls.module.db.engine.dispose()
        sys.path.remove(cls.tmp.name);sys.modules.pop('irs_lookup_test_app',None);cls.tmp.cleanup()

    def setUp(self):self.client=self.app.test_client()

    def test_new_case_clears_old_verification_and_result(self):
        self.client.get('/refund-status/start?case=WMR-2024-8554')
        with self.client.session_transaction() as session:
            session['lookup_verify']={'last_four_id':'8554','zip_code':'00000'}
            session['lookup_result']={'stale':True}
        self.client.get('/refund-status/start?case=WMR-2025-8776')
        with self.client.session_transaction() as session:
            self.assertNotIn('lookup_verify',session);self.assertNotIn('lookup_result',session)
        response=self.client.get('/refund-status/verify')
        self.assertIn(b'value="8776"',response.data)
        self.assertIn(b'value="30303"',response.data)

    def test_manually_changing_return_details_clears_previous_identity(self):
        self.client.get('/refund-status/start?case=WMR-2024-8554')
        with self.client.session_transaction() as session:
            session['lookup_verify'] = {'last_four_id': '8554', 'zip_code': '78701'}
            session['lookup_result'] = {'stale': True}
        response = self.client.post('/refund-status/start', data={
            'tax_year': '2025', 'filing_status_slug': 'head-of-household',
            'refund_amount': '2218', 'case_reference': '',
        })
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertNotIn('lookup_verify', session)
            self.assertNotIn('lookup_result', session)

    def test_same_case_keeps_intentional_mismatch_correction(self):
        self.client.get('/refund-status/start?case=WMR-2025-8665')
        with self.client.session_transaction() as session:
            session['lookup_verify']={'last_four_id':'8665','zip_code':'00000'}
        self.client.get('/refund-status/start?case=WMR-2025-8665')
        self.assertIn(b'value="00000"',self.client.get('/refund-status/verify').data)


if __name__=='__main__':unittest.main()
