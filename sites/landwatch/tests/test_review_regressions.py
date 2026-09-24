from conftest import csrf_post


def test_exact_state_match_and_combined_ranges(client):
    assert client.get('/search?q=Colorado').location.endswith('/colorado-land-for-sale')
    page = client.get('/land?priceMin=100000&priceMax=1000000&acresMin=100&acresMax=200')
    assert b'11 Listings' in page.data
    assert b'name="priceMin" value="100000"' in page.data
    assert b'name="acresMin" value="100"' in page.data


def test_saved_search_blocks_external_navigation(alice):
    response = csrf_post(alice, '/save-search', json={'url': '//example.org', 'name': 'Unsafe'})
    assert response.status_code == 400


def test_session_tokens_are_fresh_and_csrf_required(client):
    assert client.post('/log-in', data={'email': 'alice.j@test.com', 'password': 'TestPass123!'}).status_code == 400
    tokens = []
    for _ in range(2):
        csrf_post(client, '/log-in', data={'email': 'alice.j@test.com', 'password': 'TestPass123!'})
        from app import Session
        with client.application.app_context():
            tokens.append(Session.query.order_by(Session.created_at.desc()).all()[-1].token)
        csrf_post(client, '/log-out')
    assert tokens[0] != tokens[1]
    assert all(len(t) == 64 for t in tokens)


def test_inquiry_has_recipient_and_required_message(alice):
    path = '/contact/427843237'
    data = dict(name='Alice Johnson', email='alice.j@test.com', phone='5125550164', message='')
    assert csrf_post(alice, path, data=data).status_code == 400
    data['message'] = 'Please send soil reports.'
    assert csrf_post(alice, path, data=data).status_code == 302
    response = alice.get('/account')
    assert b'Devin Dye' in response.data and b'Please send soil reports.' in response.data


def test_local_gallery_and_proposed_use(client):
    page = client.get('/allen-county-ohio-farms-and-ranches-for-sale/pid/427843237')
    assert b'3 available pictures' in page.data
    assert b'>Agriculture</span>' in page.data
    assert b'Auction' in page.data and b'price not disclosed' in page.data
