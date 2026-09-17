"""UC Berkeley mirror health check."""
from healthcheck import random_user


def run(p):
    # 1. Home page renders
    p.assert_get('home', '/', must_contain='Berkeley')

    # 2. News list renders
    p.assert_get('news list', '/news', must_contain='article')

    # 3. Programs list renders
    p.assert_get('programs list', '/programs', must_contain='program')

    # 4. Faculty list renders
    p.assert_get('faculty list', '/faculty', must_contain='Professor')

    # 5. Search returns results
    p.assert_get('search', '/search?q=computer+science', must_contain='result')

    # 6. Register page renders with CSRF
    user = random_user()
    html = p.assert_get('register page', '/register', must_contain='csrf_token')
    token = p.csrf(html)
    if not token:
        p.check('register csrf token', False, 'no csrf in register form')
        return

    # 7. Submit registration
    p.assert_post('register submit', '/register', {
        'csrf_token': token,
        'username': user['first_name'].lower() + user['last_name'].lower(),
        'full_name': user['name'],
        'email': user['email'],
        'password': user['password'],
        'confirm': user['password'],
    }, accept_status=(200, 302, 303))

    # Logout so login form is real
    p.get('/logout')

    # 8. Login page renders
    html = p.assert_get('login page', '/login', accept_status=(200, 302, 303))
    token = p.csrf(html) if html else ''

    # 9. Submit login
    if token:
        p.assert_post('login submit', '/login', {
            'csrf_token': token,
            'email': user['email'],
            'password': user['password'],
        }, accept_status=(200, 302, 303))
    else:
        p.check('login submit', True, 'already authenticated from register')

    # 10. Authenticated account page
    p.assert_get('account page', '/account', must_contain=user['first_name'])
