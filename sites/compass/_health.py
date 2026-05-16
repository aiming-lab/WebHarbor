"""compass mirror health check."""
from healthcheck import random_user


def run(p):
    p.assert_get('home', '/', must_contain='Compass')
    p.assert_get('search New York', '/search?q=New York', must_contain='New York')
    p.assert_get('city for-sale', '/homes-for-sale/new-york-ny/',
                 must_contain='Homes')
    p.assert_get('agents directory', '/agents', must_contain='Agent')
    p.assert_get('open houses', '/open-houses', must_contain='Open')

    user = random_user()
    html = p.assert_get('register page', '/register')
    token = p.csrf(html)
    if not token:
        p.check('register csrf', False, 'no csrf'); return
    p.assert_post('register submit', '/register', {
        'csrf_token': token,
        'name':     f"{user['first_name']} {user['last_name']}",
        'email':    user['email'],
        'password': user['password'],
        'confirm':  user['password'],
    }, accept_status=(200, 302, 303))

    p.get('/logout')
    html = p.assert_get('login page', '/login')
    token = p.csrf(html)
    if not token:
        p.check('login csrf', False, 'no csrf'); return
    p.assert_post('login submit', '/login', {
        'csrf_token': token,
        'email':    user['email'],
        'password': user['password'],
    }, accept_status=(200, 302, 303))
    p.assert_get('account', '/account', accept_status=(200, 302))
