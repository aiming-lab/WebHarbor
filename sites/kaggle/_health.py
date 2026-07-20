"""kaggle mirror health check."""
from healthcheck import random_user


def run(p):
    p.assert_get('home', '/', must_contain='Kaggle')
    p.assert_get('competitions', '/competitions', must_contain='Competitions')
    p.assert_get('search fraud', '/search?q=fraud', must_contain='fraud')
    p.assert_get(
        'competition detail',
        '/competitions/credit-default-risk-2026',
        must_contain='ROC AUC',
    )
    p.assert_get('dataset detail', '/datasets/credit-card-fraud-transactions',
                 must_contain='About this Dataset')
    p.assert_get('rankings', '/rankings', must_contain='Rankings')

    user = random_user()
    html = p.assert_get('register page', '/register')
    token = p.csrf(html)
    if not token:
        p.check('register csrf', False, 'no csrf')
        return
    p.assert_post('register submit', '/register', {
        'csrf_token': token,
        'username': user['username'],
        'email':    user['email'],
        'password': user['password'],
        'confirm':  user['password'],
    }, accept_status=(200, 302, 303))

    p.get('/logout')

    html = p.assert_get('login page', '/login')
    token = p.csrf(html)
    if not token:
        p.check('login csrf', False, 'no csrf')
        return
    p.assert_post('login submit', '/login', {
        'csrf_token': token,
        'email':    user['email'],
        'password': user['password'],
    }, accept_status=(200, 302, 303))

    p.assert_get('account page', '/account', accept_status=(200, 302))
