from conftest import csrf_post


def variant(client, handle):
    from app import Product, ProductVariant
    with client.application.app_context():
        p = Product.query.filter_by(handle=handle).one()
        return ProductVariant.query.filter_by(product_id=p.id).first().id


def test_delivery_state_is_checked_at_checkout(client):
    vid = variant(client, '2023-time-tide-pinot-noir-monterey-county')
    with client.session_transaction() as session:
        session['ship_state'] = 'CA'
    assert csrf_post(client, '/cart/add', data={'variant_id': vid, 'quantity': 3}).status_code == 200
    details = dict(email='buyer@example.com', ship_to_name='Buyer', address_line1='100 Main St',
                   city='Salt Lake City', state='UT', zip_code='84101')
    response = csrf_post(client, '/checkout/information', data=details)
    assert b'cannot ship' in response.data
    # A previously accepted address cannot bypass the final shipping guard.
    with client.session_transaction() as session:
        session['checkout_info'] = details
        session['checkout_payment'] = 'Visa ending in 1111'
    response = csrf_post(client, '/checkout/review', data={'age_confirmed': 'on'})
    assert b'cannot ship' in response.data
    from app import Order
    with client.application.app_context():
        assert Order.query.count() == 8


def test_gift_card_has_no_wine_minimum_or_fees(client):
    vid = variant(client, 'giftcard')
    assert csrf_post(client, '/cart/add', data={'variant_id': vid, 'quantity': 1}).status_code == 200
    assert client.get('/checkout/information').status_code == 200
    from app import cart_summary
    with client.session_transaction() as sess:
        cookie = dict(sess)
    with client.application.test_request_context('/'):
        from flask import session
        session.update(cookie)
        summary = cart_summary()
        assert summary['bottles'] == summary['shipping'] == summary['processing'] == 0
        assert summary['meets_minimum']


def test_confirmation_is_private(client, alice):
    assert client.get('/checkout/confirmation/MWS1042').status_code in (403, 404)
    assert alice.get('/checkout/confirmation/MWS1042').status_code == 200


def test_csrf_covers_cart_and_state(client):
    assert client.post('/cart/add', data={}).status_code == 400
    assert client.post('/ship-state', data={'state': 'CA'}).status_code in (400, 404)


def test_article_keeps_policy_prose_without_upstream_scripts(client):
    html = client.get('/blogs/wine-101/a-guide-to-wine-storage-temperatures').get_data(as_text=True)
    assert '55' in html and '60' in html and 'Cabernet Sauvignon' in html
    assert 'gorgias.chat' not in html and 'window.shopUrl' not in html
    assert 'NewsletterKlaviyo' not in html
