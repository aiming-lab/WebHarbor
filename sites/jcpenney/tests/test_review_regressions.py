import re


def post(client, path, data):
    html = client.get('/signin').get_data(as_text=True)
    token = re.search(r'name="_csrf" value="([^"]+)"', html).group(1)
    return client.post(path, data={**data, '_csrf': token})


def test_fixed_dollar_coupon_and_threshold(client):
    from app import Coupon, coupon_discount
    with client.application.app_context():
        coupon = Coupon.query.filter_by(code='GOSHOP15').one()
        assert coupon_discount(coupon, 49.99) == 0
        assert coupon_discount(coupon, 162.37) == 10


def test_clothing_requires_available_size(client):
    data = dict(ppid='ppr5008618161', color='Moonscape', quantity='1')
    assert post(client, '/cart/add', data).status_code == 400
    assert post(client, '/cart/add', {**data, 'size': 'nonexistent'}).status_code == 400
    from app import ProductColor, Product
    with client.application.app_context():
        p = Product.query.filter_by(ppid=data['ppid']).one()
        color = next(c for c in p.colors if c.color == data['color'])
        size = next(s['size'] for s in color.sizes if s['available'])
    assert post(client, '/cart/add', {**data, 'size': size}).status_code == 302


def test_login_next_cannot_leave_site(client):
    response = post(client, '/signin?next=//example.org', dict(email='alice.j@test.com', password='TestPass123!'))
    assert response.status_code == 302
    assert response.location.startswith('/') and not response.location.startswith('//')
