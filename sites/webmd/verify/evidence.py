"""Observed browser pages and immutable SQLite snapshots; no live-state fallback."""
import html
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


def normalized(value):
    # browser-use records indexed DOM text; scripted replays use innerText.
    text = re.sub(r'<[/a-zA-Z][^>]*>|\[\d+\]', '', str(value))
    text = re.sub(r'(?m)^\s*[|*]+', '', text)
    return re.sub(r'\s+', ' ', html.unescape(text)).strip().casefold()


class Evidence:
    def __init__(self, run_dir, initial_db=None, after_db=None):
        self.root = Path(run_dir).resolve()
        self.traj = json.loads((self.root / 'trajectory.json').read_text())
        start = urlsplit(self.traj.get('start_url') or self.traj.get('web') or '')
        if start.scheme not in ('http', 'https') or not start.netloc:
            raise ValueError('A valid start_url is required')
        self.origin = (start.scheme, start.netloc)
        self.pages = []
        for index, step in enumerate(self.traj.get('steps', [])):
            url = urlsplit(step.get('url', ''))
            # Only observed pages count. An action target, query-string path,
            # screenshot alone, or claimed final answer cannot prove navigation.
            text = step.get('page_text') or step.get('observed_text') or ''
            shots = [step.get(k) for k in ('screenshot_before', 'screenshot_after', 'screenshot')]
            exists = any(self.shot_exists(s) for s in shots if s)
            if (url.scheme, url.netloc) == self.origin and text and exists:
                self.pages.append((index, url.path, parse_qs(url.query), normalized(text), step))
        self.initial = self.read_db(initial_db or self.root / 'initial.db')
        self.after = self.read_db(after_db or self.root / 'after.db')

    def shot_exists(self, filename):
        p = Path(filename)
        # agent.py uses basenames; external recorders may use screenshots/name.
        candidates = [self.root / p, self.root / 'screenshots' / p.name]
        return not p.is_absolute() and '..' not in p.parts and any(c.is_file() for c in candidates)

    @staticmethod
    def read_db(path):
        path = Path(path).resolve(strict=True)
        con = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        con.row_factory = sqlite3.Row
        try:
            if con.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('Invalid SQLite snapshot')
            names = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            data = {name: [dict(r) for r in con.execute('SELECT * FROM "' + name.replace('"', '""') + '"')] for name in names}
            for name in ('users', 'articles', 'authors', 'saved_articles', 'reading_history'):
                if name not in data:
                    raise ValueError('Missing snapshot table: ' + name)
            return data
        finally:
            con.close()

    def at(self, path, *texts, query=None):
        return [p for p in self.pages if p[1] == path and
                all(normalized(s) in p[3] for s in texts) and
                (query is None or all(p[2].get(k) == [v] for k, v in query.items()))]

    def ordered(self, groups):
        previous = -1
        for group in groups:
            later = [p[0] for p in group if p[0] > previous]
            if not later:
                return False
            previous = min(later)
        return True

    def user(self, email, after=False):
        matches = [r for r in (self.after if after else self.initial)['users'] if r['email'] == email]
        return matches[0] if len(matches) == 1 else None

    def saved(self, email, after=False):
        db = self.after if after else self.initial
        u = self.user(email, after)
        if not u:
            return []
        return [r for r in db['saved_articles'] if r['user_id'] == u['id']]

    def saved_page(self, email, after=False):
        db = self.after if after else self.initial
        ids = {r['article_id'] for r in self.saved(email, after)}
        titles = [r['title'] for r in db['articles'] if r['id'] in ids]
        # Bind observed list contents to the target account, including previous
        # saves. A saved-list URL by itself says nothing about who is logged in.
        return self.at('/account/saved', 'Log Out', *titles) if titles else []


def rows(records):
    return Counter(tuple(sorted(r.items())) for r in records)


def password_matches(user, password):
    if not user:
        return False
    try:
        import bcrypt
        return bcrypt.checkpw(password.encode(), user['password_hash'].encode())
    except (ImportError, ValueError, TypeError, KeyError):
        return False


def state_ok(e, task):
    """Precise target deltas; only actual article views may add reading history."""
    before, after = e.initial, e.after
    if before.keys() != after.keys():
        return False
    allowed = {15: {'users'}, 16: {'saved_articles'}, 17: {'users'}}.get(task, set())
    for name in before:
        if name not in allowed | {'reading_history'} and rows(before[name]) != rows(after[name]):
            return False
    # Read-only tasks must not even add history unless they explicitly log in.
    # Reading an article while signed in legitimately creates another row.
    old_history, new_history = rows(before['reading_history']), rows(after['reading_history'])
    if old_history - new_history:
        return False
    additions = list((new_history - old_history).elements())
    if additions:
        if task != 16:
            return False
        user = e.user('alice.j@test.com')
        article_ids = {a['id'] for a in before['articles'] if e.at('/articles/' + a['slug'], a['title'])}
        for row in additions:
            r = dict(row)
            if not user or r['user_id'] != user['id'] or r['article_id'] not in article_ids:
                return False
    if task == 15:
        old, new = rows(before['users']), rows(after['users'])
        added = list((new - old).elements())
        u = e.user('jordan.rivera@example.com', True)
        return (not old - new and len(added) == 1 and e.user('jordan.rivera@example.com') is None
                and u is not None and dict(added[0]) == u and u['name'] == 'Jordan Rivera'
                and password_matches(u, 'DemoPass789!'))
    if task == 16:
        old, new = rows(before['saved_articles']), rows(after['saved_articles'])
        added = list((new - old).elements())
        user = e.user('alice.j@test.com')
        article = next(a for a in before['articles'] if a['slug'] == 'gout-attacks-prevention')
        if not user or old - new or len(added) != 1:
            return False
        r = dict(added[0])
        return (r['user_id'] == user['id'] and r['article_id'] == article['id'] and
                not any(x['article_id'] == article['id'] for x in e.saved(user['email'])))
    if task == 17:
        old, new = e.user('bob.m@test.com'), e.user('bob.m@test.com', True)
        if not old or not new or old['password_hash'] == new['password_hash'] or not password_matches(new, 'NewPass456!'):
            return False
        expected = [{**r, 'password_hash': new['password_hash']} if r['id'] == old['id'] else r for r in before['users']]
        return rows(expected) == rows(after['users'])
    return True
