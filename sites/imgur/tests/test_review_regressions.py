"""Regression coverage for failures observed in the task-by-task review."""
import sqlite3
from bs4 import BeautifulSoup


def test_bad_page_returns_client_error(client):
    assert client.get('/?page=banana').status_code == 400


def test_search_labels_reflect_selection(client):
    page = BeautifulSoup(client.get('/search?q=cat&sort=time&date=day').data, 'html.parser')
    heading = page.select_one('.searchhead').get_text(' ', strip=True)
    assert 'newest' in heading and 'today' in heading
    assert 'highest scoring' not in heading and 'all time' not in heading


def test_return_urls_stay_local(client, logged_in):
    response = client.post('/signin?next=https://example.com/', data={
        'username': 'alice.j@test.com', 'password': 'TestPass123!'})
    assert response.headers['Location'] == '/'
    response = logged_in.post('/favorite/cedy3bN', data={'back': '//example.com/'})
    assert response.headers['Location'].startswith('/gallery/')


def test_reply_rejects_cross_post_and_malformed_parent(logged_in):
    for parent in ['not-a-number', '2513046815', '999999999999']:
        response = logged_in.post('/comment', data={
            'post_id': 'cedy3bN', 'parent_id': parent, 'comment': 'reply'})
        assert response.status_code == 400


def test_nested_reply_is_visible_with_exact_parent(logged_in):
    text = 'A reply to an existing reply.'
    response = logged_in.post('/comment', data={
        'post_id': '4SmuGpb', 'parent_id': '2512891839', 'comment': text},
        follow_redirects=True)
    assert response.status_code == 200
    soup = BeautifulSoup(response.data, 'html.parser')
    assert text in soup.select_one('#comment-2512891839 > .replies').get_text()
    uri = logged_in.application.config['SQLALCHEMY_DATABASE_URI']
    with sqlite3.connect(uri.removeprefix('sqlite:///')) as db:
        row = db.execute('select author_id,post_id,parent_id from comments where text=?',(text,)).fetchone()
    assert row == (990000001,'4SmuGpb',2512891839)


def test_gallery_shows_favorite_and_follow_state(logged_in):
    logged_in.post('/favorite/cedy3bN')
    logged_in.post('/follow/user/DOcelot1')
    soup = BeautifulSoup(logged_in.get('/gallery/cedy3bN').data, 'html.parser')
    assert soup.select_one('.favform button')['aria-pressed'] == 'true'
    assert soup.select_one('.favform button')['aria-label'] == 'Remove from Favorites'
    assert soup.select_one('.followmini').get_text(strip=True) == 'FOLLOWING'


def test_generated_meme_image_and_caption_metadata(logged_in):
    response = logged_in.post('/meme-generator', data={
        'template': '11', 'top_text': 'WHY DID I',
        'bottom_text': 'OPEN THE MEME GENERATOR', 'title': 'My mirror meme'},
        follow_redirects=True)
    soup = BeautifulSoup(response.data, 'html.parser')
    image_url = soup.select_one('.mediaitem img')['src']
    assert image_url.startswith('/media/uploads/meme_')
    assert '/uploads/uploads/' not in image_url
    image = logged_in.get(image_url)
    assert image.status_code == 200 and image.data.startswith(b'\xff\xd8')
    uri = logged_in.application.config['SQLALCHEMY_DATABASE_URI']
    with sqlite3.connect(uri.removeprefix('sqlite:///')) as db:
        description = db.execute("SELECT description FROM posts WHERE title='My mirror meme'").fetchone()[0]
    assert description == 'Annoyed Picard\nWHY DID I\nOPEN THE MEME GENERATOR'
    # Reusing a real runtime image must not crash on the extension capture.
    response = logged_in.post('/upload', data={'url': image_url, 'title': 'Reused meme'},follow_redirects=True)
    assert response.status_code == 200
    assert logged_in.post('/meme-generator', data={'template':'bad'}).status_code == 400
