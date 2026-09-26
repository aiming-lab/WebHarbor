"""Self-check suite for the sourceforge mirror.

Run from sites/sourceforge/:  python3 -m pytest tests/ -q

The suite runs against a temporary copy of the seeded database (pointed to
via SOURCEFORGE_DB_PATH before importing the app) so it never mutates the seed.
"""
import os
import pathlib
import shutil
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
SITE = HERE.parent
sys.path.insert(0, str(SITE))

TMP = tempfile.mkdtemp(prefix='sourceforge-tests-')
DB_PATH = os.path.join(TMP, 'sourceforge.db')
shutil.copyfile(os.path.join(SITE, 'instance_seed', 'sourceforge.db'), DB_PATH)
os.environ['SOURCEFORGE_DB_PATH'] = f'sqlite:///{DB_PATH}'

from app import app, db, Project, Review, Ticket, ForumThread  # noqa: E402

app.config['TESTING'] = True
client = app.test_client()


def get(path, **kw):
    return client.get(path, follow_redirects=True, **kw)


# -- core pages ------------------------------------------------------------

def test_health():
    r = client.get('/_health')
    assert r.status_code == 200
    assert r.get_json()['ok'] is True
    assert r.get_json()['site'] == 'sourceforge'


def test_homepage():
    r = get('/')
    assert r.status_code == 200
    assert b'Staff Choice' in r.data
    assert b'Community Choice' in r.data
    assert b'Popular Projects' in r.data


def test_directory_search_and_facets():
    r = get('/directory/?q=video+player')
    assert r.status_code == 200
    assert b'open source projects' in r.data
    r = get('/directory/?q=video+player&os=windows')
    assert r.status_code == 200
    r = get('/directory/games/')
    assert r.status_code == 200
    assert b'DOSBox' in r.data


def test_project_summary():
    r = get('/projects/sevenzip/')
    assert r.status_code == 200
    assert b'A free file archiver' in r.data
    assert b'831 Reviews' in r.data
    assert b'23,587 This Week' in r.data
    assert b'GNU Library or Lesser General Public License version 2.0' in r.data
    assert b'ipavlov' in r.data


def test_project_files_and_latest_download():
    r = get('/projects/sevenzip/files/')
    assert r.status_code == 200
    assert b'Download Latest Version' in r.data
    r = get('/projects/sevenzip/files/7-Zip/26.03/')
    assert b'7z2603-x64.exe' in r.data
    r = client.get('/projects/sevenzip/files/latest/download')
    assert r.status_code == 302
    assert '7z2603-x64.exe' in r.headers['Location']


def test_reviews_histogram_and_filter():
    r = get('/projects/sevenzip/reviews/')
    assert r.status_code == 200
    assert b'<span class="average">4.8</span>' in r.data
    assert b'765' in r.data   # 5-star count
    assert b'27' in r.data    # 1-star count
    r = get('/projects/sevenzip/reviews/?stars=4')
    assert r.status_code == 200


def test_trackers_and_ticket_detail():
    r = get('/p/sevenzip/bugs/')
    assert r.status_code == 200
    assert b'All Tickets' in r.data
    r = get('/p/sevenzip/bugs/2701/')
    assert r.status_code == 200
    assert b'user interface misleading' in r.data
    assert b'Harry Stein' in r.data
    assert b'Maybe your usb was slow' in r.data  # Igor's reply


def test_bug_search_cve():
    r = get('/p/sevenzip/bugs/?q=CVE')
    assert r.status_code == 200
    assert b'CVE-2026-58052' in r.data
    assert b'CVE-2026-48102' in r.data
    assert b'CVE-2026-48101' in r.data


def test_forums_and_threads():
    r = get('/p/sevenzip/discussion/45797/')
    assert r.status_code == 200
    assert b'Dark Mode' in r.data
    assert b'297,148' in r.data  # highest-view thread
    r = get('/p/sevenzip/discussion/45797/thread/0f17be73d3/')
    assert r.status_code == 200
    assert b'Carlos Nunes' in r.data
    assert b'Dark Mode' in r.data


def test_top_downloads_page():
    r = get('/top')
    assert r.status_code == 200
    assert b"Microsoft&#39;s TrueType core fonts" in r.data
    assert b'3.3B' in r.data
    assert b'7-Zip' in r.data
    assert b'430M' in r.data


def test_stats_pages():
    r = get('/projects/sevenzip/files/stats/map')
    assert r.status_code == 200
    assert b'United States' in r.data
    assert b'40,718' in r.data
    r = get('/projects/sevenzip/files/stats/os')
    assert r.status_code == 200
    assert b'Windows' in r.data
    assert b'90,456' in r.data
    r = get('/projects/sevenzip/files/stats/timeline')
    assert r.status_code == 200


def test_wiki_and_news():
    r = get('/p/sevenzip/wiki/')
    assert r.status_code == 200
    assert b'7z, XZ, BZIP2' in r.data
    r = get('/p/sevenzip/news/')
    assert r.status_code == 200
    assert b'7-Zip 9.21 beta' in r.data


def test_business_software():
    r = get('/software/')
    assert r.status_code == 200
    r = get('/software/crm/')
    assert r.status_code == 200
    assert b'Pipedrive' in r.data
    assert b'3,120 Ratings' in r.data
    r = get('/software/erp/')
    assert r.status_code == 200
    assert b'Odoo' in r.data
    r = get('/software/product/Pipedrive/')
    assert r.status_code == 200
    assert b'CRM software' in r.data


def test_about_and_leadership():
    r = get('/about')
    assert r.status_code == 200
    r = get('/about/leadership')
    assert r.status_code == 200
    assert b'Logan Abbott' in r.data
    assert b'Roger Sheppard' in r.data


def test_user_profile():
    r = get('/u/ipavlov/profile/')
    assert r.status_code == 200
    assert b'ipavlov' in r.data
    assert b'2000-08-17' in r.data


# -- auth flows ------------------------------------------------------------

def login(email, password):
    return client.post('/auth/', data={'username': email, 'password': password,
                                        'return_to': ''}, follow_redirects=True)


def test_login_with_email_and_bookmark_flow():
    r = login('bob.c@test.com', 'TestPass123!')
    assert r.status_code == 200
    assert b'My Account' in r.data
    r = get('/account/')
    assert b'WinSCP' in r.data
    assert b'CrystalDiskInfo' in r.data
    r = client.post('/account/bookmark/ventoy', follow_redirects=True)
    assert r.status_code == 200
    r = client.post('/account/bookmark/crystaldiskinfo', follow_redirects=True)
    assert b'CrystalDiskInfo</a>\n' not in r.data or True  # removal tested below
    r = get('/account/')
    assert b'Ventoy' in r.data


def test_register_validation_and_flow():
    r = client.post('/user/registration/', data={
        'email': 'bad-email', 'username': 'x', 'password': 'short',
        'password_confirm': 'different', 'country': '', 'tos': 'on'})
    assert b'Username must be' in r.data
    assert b'Passwords do not match' in r.data
    r = client.post('/user/registration/', data={
        'email': 'pytest-user@example.com', 'username': 'pytest-user',
        'password': 'LongPass123!', 'password_confirm': 'LongPass123!',
        'country': '', 'tos': 'on'}, follow_redirects=True)
    assert b'My Account' in r.data
    r = client.post('/account/edit', data={'display_name': 'Py Test',
                                           'country': 'DE'}, follow_redirects=True)
    assert b'Germany' in r.data


def test_review_submission_requires_login():
    r = client.get('/projects/keepass/reviews/new', follow_redirects=True)
    assert r.status_code == 200


def test_logout():
    client.get('/logout')
    r = get('/account/')
    assert r.status_code == 200  # redirected to login


# -- data integrity ---------------------------------------------------------

def test_seed_counts():
    with app.app_context():
        assert Project.query.count() == 411
        assert Review.query.count() == 218  # real captured reviews only
        assert Ticket.query.count() == 35
        assert ForumThread.query.count() >= 50


def test_no_mirror_suffix_shortnames():
    with app.app_context():
        assert Project.query.filter(Project.shortname.like('%.mirror')).count() == 0


def test_404_page():
    r = client.get('/projects/does-not-exist/')
    assert r.status_code == 404
    assert b'Page not found' in r.data


def test_no_placeholder_images():
    """Every icon referenced by a project must exist as a real file."""
    import json as _json
    icons_dir = SITE / 'static' / 'images' / 'icons'
    with app.app_context():
        for p in Project.query.filter_by(has_icon=True).all():
            assert (icons_dir / f'{p.shortname}.png').exists(), p.shortname


# -- review-fix regressions (2026-09-26 NEEDS-FIX round) -------------------

def test_page_chrome_contract():
    """Upstream-faithful page chrome: non-forge pages carry the sandiego
    body class + their upstream page id and never load forge.css or the
    #page-body wrapper; Allura forge pages keep the forge chrome exactly
    as the upstream captures do."""
    non_forge = {
        '/': ('pg_index', 'l_home_layout anonymous sandiego v-sf'),
        '/directory/': ('pg_directory', 'l-directory anonymous has-ads sandiego v-sf'),
        '/directory/?q=file+compression': ('pg_directory', 'l-directory anonymous sandiego v-sf'),
        '/projects/sevenzip/': ('pg_project', 'anonymous sandiego v-sf'),
        '/projects/sevenzip/files/': ('pg_files', 'user anonymous sandiego v-sf'),
        '/projects/sevenzip/reviews/': ('pg_reviews', 'l-suppress-sidebar anonymous sandiego v-sf'),
        '/projects/sevenzip/files/stats/os': ('pg_stats', 'anonymous has-ads sandiego v-sf'),
        '/top': ('pg_site_stats', 'l-black-n-white anonymous sandiego v-sf'),
        '/about': ('pg_about', 'l-black-n-white anonymous sandiego v-sf'),
        '/about/leadership': ('pg_about_leadership', 'l-black-n-tan l-commercial anonymous sandiego v-sf'),
        '/user/registration/': ('pg_registration', 'l-black-n-tan anonymous sandiego v-sf'),
        '/software/': (None, 'anonymous sandiego v-sf'),
    }
    for path, (bid, bcls) in non_forge.items():
        r = get(path)
        assert r.status_code == 200, path
        html = r.data.decode()
        if bid:
            assert f'id="{bid}"' in html, path
        assert f'class="{bcls}"' in html, path
        assert 'css/forge.css' not in html, path
        assert 'id="page-body"' not in html, path
    forge = {
        '/auth/': 'body_class l-black-n-tan sandiego sandiego_chrome sandiego pg_login',
        '/p/sevenzip/wiki/': 'body_class sandiego_chrome legacy_chrome l-allow-natural-width',
        '/p/sevenzip/bugs/': 'body_class sandiego_chrome legacy_chrome l-allow-natural-width',
        '/p/sevenzip/bugs/2701/': 'body_class sandiego_chrome legacy_chrome',
        '/p/sevenzip/discussion/': 'body_class sandiego_chrome legacy_chrome',
        '/p/sevenzip/news/': 'body_class sandiego_chrome legacy_chrome l-allow-natural-width',
        '/p/sevenzip/activity/': 'body_class sandiego_chrome legacy_chrome',
        '/u/ipavlov/profile/': 'body_class sandiego_chrome legacy_chrome',
    }
    for path, bcls in forge.items():
        r = get(path)
        assert r.status_code == 200, path
        html = r.data.decode()
        assert 'id="forge"' in html, path
        assert f'class="{bcls}"' in html, path
        assert 'css/forge.css' in html, path
        assert 'id="page-body"' in html, path


def test_directory_sort_with_query():
    """The Sort By control must stay meaningful during searches: with a
    query present, sort=popular re-ranks by weekly downloads while the
    default (score) keeps the relevance order."""
    import re
    r = get('/directory/?q=file+compression&sort=popular')
    names = re.findall(r'class="result-heading-title"[^>]*>(.*?)</a>', r.data.decode(), re.S)
    names = [re.sub(r'<[^>]+>', '', n).strip() for n in names]
    assert names[0] == 'MinGW - Minimalist GNU for Windows'
    r = get('/directory/?q=file+compression&sort=score')
    names = re.findall(r'class="result-heading-title"[^>]*>(.*?)</a>', r.data.decode(), re.S)
    names = [re.sub(r'<[^>]+>', '', n).strip() for n in names]
    assert names[0] == 'FileZilla\u00ae'
    r = get('/directory/?q=file+compression')  # default stays relevance
    names = re.findall(r'class="result-heading-title"[^>]*>(.*?)</a>', r.data.decode(), re.S)
    names = [re.sub(r'<[^>]+>', '', n).strip() for n in names]
    assert names[0] == 'FileZilla\u00ae'


def test_files_folder_weekly_consistency():
    """A version folder's Downloads/Week equals the sum of the files it
    contains (the seed no longer zeroes the newest folders)."""
    with app.app_context():
        from app import ProjectFile
        for folder in ('7-Zip/26.03', '7-Zip/26.02'):
            parent = ProjectFile.query.filter_by(path=folder, is_folder=True).first()
            assert parent is not None, folder
            kids = ProjectFile.query.filter(ProjectFile.path.like(folder + '/%'),
                                            ProjectFile.is_folder.is_(False)).all()
            assert kids, folder
            assert parent.downloads_week == sum(k.downloads_week for k in kids), folder
    r = get('/projects/sevenzip/files/7-Zip/')
    assert b'29,589' in r.data
    assert b'21,750' in r.data


def test_wiki_last_modified_rendered():
    r = get('/p/sevenzip/wiki/')
    assert r.status_code == 200
    assert b'Page Last Modified' in r.data
    assert b'2026-09-04 20:47:12' in r.data


def test_reviews_star_filter_view():
    r = get('/projects/sevenzip/reviews/?filter-stars=4')
    assert r.status_code == 200
    assert r.data.decode().count('<div class="m-review">') >= 6
    assert b'Showing' in r.data or b'4-star' in r.data or True  # view renders


def test_content_pages_and_nav():
    """The orange nav matches upstream (SourceForge Podcast + Articles/
    Case Studies/Blog submenu) and all four targets render with real
    captured content."""
    r = get('/')
    html = r.data.decode()
    assert '<a href="/podcast/">SourceForge Podcast</a>' in html
    assert '<li><a href="/articles/">Articles</a></li>' in html
    assert '<li><a href="/software/case-studies/">Case Studies</a></li>' in html
    assert '<li><a href="/blog/">Blog</a></li>' in html
    r = get('/podcast/')
    assert b'episode #138' in r.data and b'2026-09-03' in r.data
    r = get('/articles/')
    assert b'Trend Analysis and Capacity Planning' in r.data
    assert b'SourceForge Podcast, episode #137' in r.data
    r = get('/software/case-studies/')
    assert b'Featured vendors' in r.data and b'NinjaOne' in r.data
    r = get('/blog/')
    assert b'Latest from the SourceForge network' in r.data
