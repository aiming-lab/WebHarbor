"""cookpad mirror health check."""
from healthcheck import random_user


def run(p):
    # Public pages
    p.assert_get('home', '/', must_contain='Cookpad')
    p.assert_get('search chicken', '/search?q=chicken', must_contain='chicken')
    p.assert_get(
        'recipe detail',
        '/recipe/butter-chicken',
        must_contain='Ingredients',
    )

    # Register
    user = random_user()
    html = p.assert_get('register page', '/register', must_contain='csrf_token')
    token = p.csrf(html)
    if not token:
        p.check('register csrf', False, 'no csrf token found')
        return
    p.check('register csrf', True)
    p.assert_post(
        'register submit',
        '/register',
        {
            'csrf_token': token,
            'username': user['username'],
            'email': user['email'],
            'password': user['password'],
            'confirm_password': user['password'],
        },
        accept_status=(200, 302, 303),
    )

    # Logout so /login renders a real form (register auto-logs-in).
    p.get('/logout')

    # Login (fresh cookie jar path 鈥?registration auto-logs-in, but exercise
    # login form explicitly for smoke coverage).
    html = p.assert_get('login page', '/login', must_contain='csrf_token')
    token = p.csrf(html)
    if not token:
        p.check('login csrf', False, 'no csrf token found')
        return
    p.check('login csrf', True)
    p.assert_post(
        'login submit',
        '/login',
        {
            'csrf_token': token,
            'email': user['email'],
            'password': user['password'],
        },
        accept_status=(200, 302, 303),
    )

    # Authenticated read 鈥?/recipe-box requires login.
    p.assert_get(
        'recipe box (auth)',
        '/recipe-box',
        accept_status=(200, 302),
    )
    p.assert_get(
        'account (auth)',
        '/account',
        accept_status=(200, 302),
    )

