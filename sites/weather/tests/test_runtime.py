import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

class Routes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();source=Path(__file__).resolve().parents[1]/'app.py'
        os.environ['WEBSYN_DB_PATH']=str(Path(cls.temp.name)/'weather.db')
        spec=importlib.util.spec_from_file_location('weather_test_app',source);cls.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.module)
        os.environ.pop('WEBSYN_DB_PATH');cls.app=cls.module.app;cls.app.config.update(TESTING=True,WTF_CSRF_ENABLED=False)
    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():cls.module.db.engine.dispose()
        cls.temp.cleanup()
    def setUp(self):
        self.client=self.app.test_client();self.client.post('/login',data={'email':'carol.d@test.com','password':'TestPass123!'})
    def test_metric_search_and_detail_agree(self):
        self.assertIn('14°C',self.client.get('/search?q=Tokyo').text)
        self.assertIn('14°C',self.client.get('/weather/tokyo-jp').text)
    def test_alert_page_is_linked(self):
        self.assertIn('href="/weather/miami-fl/alerts"',self.client.get('/weather/miami-fl').text)
        self.assertIn('February 16, 2:00 AM',self.client.get('/weather/miami-fl/alerts').text)
    def test_radar_is_honest_about_missing_local_coverage(self):
        text=self.client.get('/radar/reykjavik-is').text
        self.assertIn('Local radar imagery is unavailable',text)
        self.assertNotIn('00-us-wxhi1-1280x720.jpg',text)
    def test_home_accepts_only_saved_places(self):
        with self.app.app_context():
            m=self.module;user=m.User.query.filter_by(email='carol.d@test.com').one();old=user.home_location_id
            bad=m.Location.query.filter_by(slug='london-uk').one().id;good=m.Location.query.filter_by(slug='seattle-wa').one().id
        self.assertEqual(self.client.post('/account',data={'home_location_id':bad}).status_code,400)
        with self.app.app_context():self.assertEqual(self.module.User.query.filter_by(email='carol.d@test.com').one().home_location_id,old)
        self.assertEqual(self.client.post('/account',data={'home_location_id':good}).status_code,302)
        text=self.client.get('/').text
        self.assertIn('Seattle, WA',text);self.assertIn('8°C',text)
        self.assertEqual(self.client.post('/account',data={'home_location_id':old}).status_code,302)
    def test_invalid_units_are_rejected_without_changes(self):
        self.assertEqual(self.client.post('/account',data={'preferred_units':'kelvin','full_name':'Changed'}).status_code,400)
        with self.app.app_context():
            u=self.module.User.query.filter_by(email='carol.d@test.com').one();self.assertEqual(u.preferred_units,'metric');self.assertEqual(u.full_name,'Carol Diaz')
    def test_current_home_cannot_be_removed(self):
        self.client.post('/account/remove-location/miami-fl')
        with self.app.app_context():
            m=self.module;u=m.User.query.filter_by(email='carol.d@test.com').one();self.assertIsNotNone(m.SavedLocation.query.filter_by(user_id=u.id,location_id=u.home_location_id).first())
    def test_unsaved_location_can_be_added(self):
        self.client.post('/account/save-location/london-uk')
        self.assertIn('London, England',self.client.get('/account').text)
        self.client.post('/account/remove-location/london-uk')

if __name__=='__main__':unittest.main()
