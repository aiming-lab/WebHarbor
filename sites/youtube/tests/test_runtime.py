import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

class Routes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        source = Path(__file__).resolve().parents[1] / 'app.py'
        os.environ['WEBSYN_DB_PATH'] = str(Path(cls.temp.name) / 'youtube.db')
        spec = importlib.util.spec_from_file_location('youtube_test_app', source)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)
        os.environ.pop('WEBSYN_DB_PATH')
        cls.app = cls.module.app
        cls.app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context(): cls.module.db.engine.dispose()
        cls.temp.cleanup()
    def test_nonsense_search_does_not_return_trending_videos(self):
        response = self.app.test_client().get('/results?search_query=zzzxqvnonexistent')
        self.assertIn('0 videos', response.text)
        self.assertNotIn('class="result-row"', response.text)
    def test_real_query_keeps_relevant_video(self):
        response = self.app.test_client().get('/results?search_query=flagship+phones')
        self.assertIn('R.I.P. Normal Flagship Phones', response.text)
        self.assertNotIn('1 Day vs 50,000 Day Build Challenge', response.text)
    def test_missing_avatar_uses_initials(self):
        client=self.app.test_client();client.post('/login',data={'email':'alice.j@test.com','password':'TestPass123!'})
        response=client.get('/account')
        self.assertNotIn('c_067_avatar.jpg',response.text)
        self.assertIn('Marques Brownlee',response.text)
    def test_channel_does_not_show_old_synthetic_name(self):
        response=self.app.test_client().get('/channel/night-shift-jazz')
        self.assertIn('Magic Club',response.text)
        self.assertNotIn('night-shift-jazz-banner',response.text)

if __name__=='__main__':unittest.main()
