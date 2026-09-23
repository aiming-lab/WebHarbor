"""Build-time snapshot import: catalog preservation and byte-stable re-import."""
import importlib.util
import json
from pathlib import Path
import plistlib
import sqlite3
import tempfile
import unittest
from copy import deepcopy

spec = importlib.util.spec_from_file_location(
    'imdb_homepage_seed', Path(__file__).resolve().parents[1] / 'seed_homepage.py')
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)

feature_spec = importlib.util.spec_from_file_location(
    'imdb_feature_seed', Path(__file__).resolve().parents[1] / 'seed_feature.py')
feature_seed = importlib.util.module_from_spec(feature_spec)
feature_spec.loader.exec_module(feature_seed)


class HomepageSeedTests(unittest.TestCase):
    def test_feature_snapshot_import_is_sourced_local_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / 'imdb.db'
            static = root / 'static'
            poster = static / 'images/home/source.jpg'
            poster.parent.mkdir(parents=True)
            poster.write_bytes(b'source-image')
            snapshot = root / 'feature.json'
            snapshot.write_text(json.dumps({
                'feature_id': 'featured-today-1',
                'source_url': 'https://www.imdb.com/most-anticipated/this-month/',
                'observed_at': '2026-09-12T01:02:03Z',
                'page_title': 'Source feature',
                'page_subtitle': 'Source description',
                'hero_image_path': 'images/home/source.jpg',
                'hero_image_sha256': feature_seed.digest(b'source-image'),
                'items': [{
                    'position': 1,
                    'source_id': 'tt1234567',
                    'title': 'Source title',
                    'source_url': 'https://www.imdb.com/title/tt1234567/',
                    'poster_path': 'images/home/source.jpg',
                    'poster_sha256': feature_seed.digest(b'source-image'),
                    'release_context': 'In theaters September 12',
                    'description': 'Observed description.',
                    'featuring': ['Source Person'],
                }],
            }))
            with sqlite3.connect(database) as con:
                con.execute('CREATE TABLE titles (id INTEGER PRIMARY KEY, name TEXT)')
                con.execute("INSERT INTO titles VALUES (1, 'Preserved')")
                con.execute('''CREATE TABLE home_features (
                    id VARCHAR(80) PRIMARY KEY, kind VARCHAR(30) NOT NULL,
                    position INTEGER NOT NULL, heading TEXT NOT NULL, subtitle TEXT,
                    image_path TEXT, poster_path TEXT, source_url TEXT NOT NULL,
                    captured_at VARCHAR(40) NOT NULL, payload JSON NOT NULL)''')
                con.execute('''INSERT INTO home_features VALUES
                    ('featured-today-1','editorial',1,'Old heading','Old subtitle','','',
                     'https://www.imdb.com/','2026-09-10','{"type":"list"}')''')
            result = feature_seed.import_snapshot(snapshot, database, static)
            self.assertEqual(result['items'], 1)
            self.assertEqual(result['protected_tables_unchanged'], ['titles'])
            with sqlite3.connect(database) as con:
                self.assertEqual(con.execute('SELECT * FROM titles').fetchall(), [(1, 'Preserved')])
                payload = json.loads(con.execute(
                    "SELECT payload FROM home_features WHERE id='featured-today-1'").fetchone()[0])
            self.assertEqual(payload['items'][0]['title'], 'Source title')
            self.assertNotIn('poster_source_url', payload['items'][0])
            before = database.read_bytes()
            feature_seed.import_snapshot(snapshot, database, static)
            self.assertEqual(database.read_bytes(), before)

    def test_feature_snapshot_rejects_external_or_missing_media(self):
        base = {
            'feature_id': 'featured-today-1',
            'source_url': 'https://www.imdb.com/most-anticipated/this-month/',
            'observed_at': '2026-09-12T01:02:03Z',
            'page_title': 'Source feature',
            'page_subtitle': 'Source description',
            'hero_image_path': 'images/home/missing.jpg',
            'hero_image_sha256': '0' * 64,
            'items': [],
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            database = root / 'imdb.db'
            with sqlite3.connect(database) as con:
                con.execute('''CREATE TABLE home_features (
                    id VARCHAR(80) PRIMARY KEY, kind VARCHAR(30) NOT NULL,
                    position INTEGER NOT NULL, heading TEXT NOT NULL, subtitle TEXT,
                    image_path TEXT, poster_path TEXT, source_url TEXT NOT NULL,
                    captured_at VARCHAR(40) NOT NULL, payload JSON NOT NULL)''')
                con.execute('''INSERT INTO home_features VALUES
                    ('featured-today-1','editorial',1,'Old','','','',
                     'https://www.imdb.com/','2026-09-10','{}')''')
            snapshot = root / 'feature.json'
            snapshot.write_text(json.dumps(base))
            with self.assertRaisesRegex(ValueError, 'media'):
                feature_seed.import_snapshot(snapshot, database, root / 'static')
            invalid = dict(base, source_url='https://example.com/not-imdb')
            snapshot.write_text(json.dumps(invalid))
            with self.assertRaisesRegex(ValueError, 'IMDb'):
                feature_seed.import_snapshot(snapshot, database, root / 'static')

    def test_starmeter_keeps_observed_rank_and_optional_fields(self):
        props = {'pageData': {'chartNames': {'edges': [
            {'currentRank': 7, 'node': {'id': 'nm123', 'nameText': {'text': 'Source Person'},
                'primaryImage': {'url': 'https://m.media-amazon.com/a.jpg'},
                'professions': [{'profession': {'text': 'Actor'}}],
                'knownForV2': {'credits': [{'title': {'id': 'tt123',
                    'titleText': {'text': 'Source Film'}}}]}}},
            {'currentRank': 2, 'node': {'id': 'nm456', 'nameText': {'text': 'Another Person'}}},
        ]}}}
        entries = seed.starmeter_entries(props)
        self.assertEqual([entry['rank'] for entry in entries], [7, 2])
        self.assertEqual(entries[0]['professions'], ['Actor'])
        self.assertEqual(entries[0]['known_for'], ['Source Film'])
        self.assertEqual(entries[1]['image'], '')
        self.assertEqual(entries[1]['professions'], [])
        self.assertNotIn('rank_change', entries[1], 'Do not fabricate chart movements')
        invalid = deepcopy(props)
        invalid['pageData']['chartNames']['edges'][1]['currentRank'] = 7
        with self.assertRaisesRegex(ValueError, 'rank'):
            seed.starmeter_entries(invalid)
        invalid = deepcopy(props)
        del invalid['pageData']['chartNames']['edges'][0]['currentRank']
        with self.assertRaises(ValueError):
            seed.starmeter_entries(invalid)

    def test_chart_only_archive_preserves_homepage_and_is_idempotent(self):
        props = {'requestContext': {'timestamp': '2026-09-10T15:18:46Z'},
                 'pageData': {'chartNames': {'edges': [
                     {'currentRank': 3, 'node': {'id': 'nm123',
                        'nameText': {'text': 'Source Person'}}}]}}}
        html = '<script id="__NEXT_DATA__">' + json.dumps({'props': {'pageProps': props}}) + '</script>'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'source.webarchive'
            archive.write_bytes(plistlib.dumps({'WebMainResource': {
                'WebResourceURL': 'https://www.imdb.com/chart/starmeter/',
                'WebResourceData': html.encode()}}))
            database = root / 'imdb.db'
            with sqlite3.connect(database) as con:
                con.execute('CREATE TABLE titles (id INTEGER PRIMARY KEY, name TEXT)')
                con.execute("INSERT INTO titles VALUES (1, 'Preserved')")
            result = seed.import_archive(archive, database, root / 'static')
            self.assertEqual(result['features'], 1)
            with sqlite3.connect(database) as con:
                self.assertEqual(con.execute('SELECT kind,position FROM home_features').fetchall(), [('starmeter', 3)])
                con.execute("INSERT INTO home_features VALUES ('topic-1','topic',1,'Preserved','','','','https://www.imdb.com/','2026-09-10','{}')")
            before = database.read_bytes()
            seed.import_archive(archive, database, root / 'static')
            self.assertEqual(database.read_bytes(), before)

    def test_import_preserves_catalog_and_second_import_preserves_bytes(self):
        props = {
            'requestContext': {'timestamp': '2026-09-10T13:37:06Z'},
            'cmsContext': {'transformedPlacements': {
                'pill-1': {'transformedArguments': {
                    'displayTitle': 'Source topic', 'linkTargetUrl': '/source-topic/'}}}},
            'pageQueryData': {'data': {'news': {'edges': []}}},
        }
        html = '<script id="__NEXT_DATA__">' + json.dumps({'props': {'pageProps': props}}) + '</script>'
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'source.webarchive'
            archive.write_bytes(plistlib.dumps({'WebMainResource': {
                'WebResourceURL': 'https://www.imdb.com/',
                'WebResourceData': html.encode()}}))
            database = root / 'imdb.db'
            with sqlite3.connect(database) as con:
                con.execute('CREATE TABLE titles (id INTEGER PRIMARY KEY, name TEXT)')
                con.execute('INSERT INTO titles VALUES (1, ?)', ('Original title',))
            result = seed.import_archive(archive, database, root / 'static')
            self.assertEqual(result['features'], 1)
            before = database.read_bytes()
            seed.import_archive(archive, database, root / 'static')
            self.assertEqual(database.read_bytes(), before)
            with sqlite3.connect(database) as con:
                self.assertEqual(con.execute('SELECT * FROM titles').fetchall(), [(1, 'Original title')])
                self.assertEqual(con.execute('SELECT heading FROM home_features').fetchall(), [('Source topic',)])
                con.execute("INSERT INTO home_features VALUES ('birthday-nm1', 'birthday', 1, 'Person', '', '', '', 'https://www.imdb.com/name/nm1/', '2026-09-10', '{}')")
            before = database.read_bytes()
            seed.import_archive(archive, database, root / 'static')
            self.assertEqual(database.read_bytes(), before, 'An unloaded archive must preserve prior loaded collections')

    def test_episode_labels_are_taken_from_the_source(self):
        page = seed.SourcePage('<button role="tab" aria-label="Episode 3 of 8, rated 7.9/10: Do You Reject Satan?. Select enter for more details"></button>')
        self.assertEqual(page.episodes, [{'number': 3, 'rating': '7.9', 'title': 'Do You Reject Satan?'}])

    def test_episode_details_keep_their_own_media_plot_and_identity(self):
        page = seed.SourcePage('''<div class="EpisodeRatingCard_card__abc" role="tabpanel">
            <img src="https://m.media-amazon.com/still.jpg">
            <ul class="EpisodeRatingCard_episodeInfo__abc"><li>S2.E3</li><li>Thu, Sep 3, 2026</li></ul>
            <a href="/title/tt123/?ref_=home"><h3 class="ipc-title__text">Third &amp; Final</h3></a>
            <div class="EpisodeRatingCard_plot__abc"><p>Actual source plot.</p></div></div>''')
        self.assertEqual(page.episode_details, [{'image': 'https://m.media-amazon.com/still.jpg',
            'info': 'S2.E3 Thu, Sep 3, 2026 ', 'title': 'Third & Final ',
            'plot': 'Actual source plot. ', 'source_path': '/title/tt123/'}])

    def test_loaded_cards_keep_optional_source_fields_optional(self):
        page = seed.SourcePage('''
          <div data-testid="streaming-picks-tab-container"><button role="tab" aria-selected="true">PRIME VIDEO</button></div>
          <div class="ipc-poster-card streaming-picks-title"><img src="https://m.media-amazon.com/a.jpg">
            <a class="ipc-poster-card__title" href="/title/tt123/?ref_=home"><span>Example &amp; Co</span></a>
            <span class="ipc-rating-star--rating">7.4</span></div>
          <section data-testid="rttv-parent"><div class="ipc-poster-card">
            <a class="ipc-poster-card__title" href="/title/tt456/">Future show</a>
            <a data-testid="rttv-episode-num" href="/title/tt789/">New: Season 1</a>
            <div data-testid="rttv-air-date">Wed, Sep 16</div></div></section>
          <div data-testid="name-born-today-card"><a href="/name/nm123/">
            <div data-testid="born-today-name">Person</div></a></div>''')
        self.assertEqual(page.service, 'PRIME VIDEO')
        self.assertEqual([c['kind'] for c in page.cards], ['streaming', 'tv_schedule', 'birthday'])
        self.assertEqual(page.cards[0]['heading'], 'Example & Co')
        self.assertEqual(page.cards[0]['source_path'], '/title/tt123/')
        self.assertEqual(page.cards[1]['episode_path'], '/title/tt789/')
        self.assertEqual(page.cards[1]['rating'], '')
        self.assertEqual(page.cards[2]['age'], '')


if __name__ == '__main__':
    unittest.main()
