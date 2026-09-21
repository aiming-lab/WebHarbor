"""Additional deterministic contracts for IGN tasks.

Frozen before/after snapshots are required. Assertions concern complete values,
requested rows and on-site routes. No LLM is needed to reject a bad completion.
Comparison answers support named prose, bullets and simple entity/value tables;
implicit references, double negation and arbitrary linguistic inference are not
claimed to be supported. See README.md and the regression tests for coverage.
"""
from copy import deepcopy
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qs, unquote, urlsplit

from verify_lib import norm, resolve_db

SLUGS = {
    0: 'grand-theft-auto-controversies',
    1: 'gta-online-weekly-updates',
    2: 'will-nintendo-ever-stop-making-physical-games-nvc-clips',
    6: 'walmart-has-the-lowest-price-on-a-geforce-rtx-5070-prebuilt-gaming-pc-in-2026',
    7: 'silo-season-3-review',
    8: 'playstations-physical-media-free-future-isnt-just-concerning-its-offensive-video',
    9: 'mtg-marvel-collector-boosters-amazon-sealed-in-stock',
    10: 'fortnite',
    11: 'whats-new-on-hbo-max-july-2026',
    12: 'playstations-physical-media-free-future-isnt-just-concerning-its-offensive',
    15: 'all-gta-5-cheat-codes-and-secrets-for-pc-and-console',
    16: 'dragon-ball-xenoverse-2-official-future-saga-chapter-4-trailer',
    18: 'anne-hathaway-quit-knocked-up-because-she-didnt-want-the-crowning-of-the-baby-to-be-visually-representative-seth-rogen-says',
}
EMAILS = dict(zip(
    [0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 18],
    ['alice.j', 'alice.j', 'bob.c', 'david.k', 'carol.d', 'bob.c', 'alice.j',
     'david.k', 'carol.d', 'carol.d', 'david.k', 'alice.j', 'bob.c', 'alice.j',
     'bob.c', 'alice.j', 'david.k']))
SAVE = {0: ('Games', 'gta controversy timeline'), 6: ('Deals', None),
        9: ('Deals', 'sealed booster watch'), 10: (None, 'weekly quests'),
        12: ('Read Later', None), 18: ('Weekend', 'casting anecdote')}
PLAYLIST = {2: (None, 'physical games debate'), 8: ('watching', None),
            11: (None, None), 16: ('queued', None)}


def comparison_answer(answer, task):
    """Bind positive/negative statements to the two named candidates."""
    aliases = ((r'\bturtle\s+beach(?:\s+stealth\s+pro(?:\s+(?:ii|2))?)?\b|\bstealth\s+pro(?:\s+(?:ii|2))?\b',
                r'\bcorsair(?:\s+one(?:\s+a600)?)?\b|\bone\s+a600\b') if task == 4 else
               (r'\b(?:amazon\s+)?prime\s+video\b|\bamazon\s+prime\b', r'\bhbo(?:\s+max)?\b'))
    text = str(answer or '').casefold().replace('’', "'")
    text = re.sub(aliases[0], 'TARGET', text)
    text = re.sub(aliases[1], 'OTHER', text)
    positive = False
    # Contrast conjunctions delimit assertions without discarding their polarity.
    for clause in re.split(r'[.!?;\n]+|\b(?:but|whereas|while)\b', text):
        mentions = list(re.finditer(r'TARGET|OTHER', clause))
        if not mentions:
            continue
        # Reading/opening/comparing a page is not asserting the requested fact.
        navigation_only = bool(re.search(r'\b(?:read|opened|visited|compared|considered)\b', clause)) and not re.search(
            r'\b(?:has|have|includes?|lists?|tagged|answer|yes|no)\b', clause)
        if navigation_only:
            continue
        if re.search(r'\b(?:maybe|perhaps|unsure|uncertain|guess|cannot tell|can.t tell)\b', clause):
            return False
        for n, mention in enumerate(mentions):
            previous = mentions[n - 1].end() if n else 0
            end = mentions[n + 1].start() if n + 1 < len(mentions) else len(clause)
            prefix = clause[previous:mention.start()]
            tail = clause[mention.end():end]
            # In "TARGET, not OTHER", not scopes to OTHER, not TARGET.
            tail = re.sub(r'[,\s]*(?:(?:and|or|rather than|instead of|unlike)\s+)?not\s*$', '', tail) if n + 1 < len(mentions) else tail
            negative_prefix = bool(re.search(r'\b(?:not|unlike|rather than|instead of)\s*$', prefix))
            negative_tail = bool(re.search(r"\b(?:not(?!\s+only)|no|never|neither|without|lacks?|absent|doesn't|doesnt|isn't|isnt|does not|is not|doesn.t)\b", tail))
            negative = negative_prefix or negative_tail
            if mention.group() == 'TARGET':
                if negative:
                    return False
                positive = True
            elif not negative:
                return False
    return positive


def snapshot(path):
    if not path or not Path(path).is_file():
        raise ValueError('required database snapshot unavailable')
    result = {}
    with sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        for (table,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            quoted = table.replace('"', '""')
            rows = [dict(row) for row in db.execute(f'SELECT * FROM "{quoted}"')]
            if any('id' not in row for row in rows):
                raise ValueError('table without stable row identity')
            result[table] = {row['id']: row for row in rows}
    required = {'users', 'content_items', 'saved_items', 'playlist_entries', 'comments',
                'guide_progress', 'alert_subscriptions', 'sections', 'digests'}
    if not required <= result.keys():
        raise ValueError('incomplete database schema')
    return result


def one(state, table, **fields):
    rows = [r for r in state[table].values() if all(r.get(k) == v for k, v in fields.items())]
    if len(rows) > 1:
        raise ValueError(f'ambiguous {table} target')
    return rows[0] if rows else None


def site_urls(t):
    origin = urlsplit(t.get('start_url', ''))
    if origin.scheme not in ('http', 'https') or not origin.netloc:
        return []
    urls = []
    for step in t.get('steps', []):
        try:
            p = urlsplit(step.get('url', ''))
            if (p.scheme, p.netloc) == (origin.scheme, origin.netloc):
                urls.append(p)
        except ValueError:
            continue
    return urls


def route_for(item):
    if item['content_type'] == 'guide':
        return item['source_path']
    return ('/videos/' if item['content_type'] == 'video' else '/articles/') + item['slug']


def check_contract(j, trajectory, args):
    def require(condition, name):
        if not j.check(name, condition):
            raise ValueError(name)

    try:
        task = int(j.task_id.split('--')[-1])
        before = snapshot(resolve_db(args.initial_db, args.container, 'instance_seed'))
        after = snapshot(resolve_db(args.after_db, args.container, 'instance'))
        expected = deepcopy(before)
        require(before.keys() == after.keys(), 'snapshot_schema_matches')
        urls = site_urls(trajectory)
        paths = [unquote(p.path).rstrip('/') or '/' for p in urls]
        if task in EMAILS:
            user = one(before, 'users', email=EMAILS[task] + '@test.com')
            require(user is not None, 'initial_user_exists')
            uid = user['id']
        item = None
        if task in SLUGS:
            item = one(before, 'content_items', slug=SLUGS[task])
            require(item is not None, 'initial_target_exists')
            require(route_for(item).rstrip('/') in paths, 'visited_exact_target_route')
            iid = item['id']
        if task in (0, 6, 12, 17):
            required_queries = {0: ['GTA Controversies'],
                                6: ['GeForce RTX 5070'], 12: ['physical media future'],
                                17: ['HBO Max July', 'Amazon Prime Video July']}[task]
            # A search must be performed for the requested subject. Extra words
            # and ordinary punctuation are harmless; unrelated queries are not.
            queries = [norm(parse_qs(p.query).get('q', [''])[0]) for p in urls if p.path == '/search']
            require(all(any(all(word in re.findall(r'\w+', q) for word in re.findall(r'\w+', norm(query)))
                                for q in queries) for query in required_queries), 'requested_search_performed')
        if task in (8, 9, 11, 18):
            section = {8: ['/videos'], 9: ['/deals'], 11: ['/tv', '/news/television'],
                       18: ['/movies', '/news/movies']}[task]
            require(any(p in paths for p in section), 'visited_requested_section')
        if task in (4, 17):
            pair = (['turtle-beach-stealth-pro-ii-review', 'corsair-one-a600-review'] if task == 4 else
                    ['whats-new-on-amazon-prime-video-july-2026', 'whats-new-on-hbo-max-july-2026'])
            for slug in pair:
                target = one(before, 'content_items', slug=slug)
                require(target is not None and route_for(target) in paths, 'visited_comparison_detail')
            if task == 4:
                require(any(p.path in ('/reviews', '/reviews/tech') and
                            parse_qs(p.query).get('genre', [''])[0] == 'tech' for p in urls), 'used_tech_genre_filter')
            require(comparison_answer(trajectory.get('final_answer'), task), 'answer_entity_and_polarity')
        elif task in SAVE or task in PLAYLIST or task in (1, 15):
            table = 'saved_items' if task in SAVE else 'playlist_entries' if task in PLAYLIST else 'guide_progress'
            keys = {'user_id': uid, 'item_id': iid}
            if table == 'guide_progress':
                keys['checkpoint'] = 'Claim Independence Day freebies' if task == 1 else 'Read overview'
            old = one(before, table, **keys)
            new = one(after, table, **keys)
            require(new is not None and new != old, 'requested_row_changed')
            if table == 'saved_items':
                folder, note = SAVE[task]
                require(folder is None or norm(new['folder']) == norm(folder), 'exact_saved_folder')
                require(note is None or norm(new['note']) == norm(note), 'exact_saved_note')
                allowed = ({'folder'} if folder is not None else set()) | ({'note'} if note is not None else set())
            elif table == 'playlist_entries':
                status, note = PLAYLIST[task]
                require(new['status'] in ('queued', 'watching', 'watched'), 'valid_playlist_status')
                require(status is None or norm(new['status']) == status, 'exact_playlist_status')
                require(note is None or norm(new['note']) == note, 'exact_playlist_note')
                allowed = ({'status'} if status is not None else set()) | ({'note'} if note is not None else set())
            else:
                require(new['completed'] == 1, 'checkpoint_complete')
                allowed = {'completed', 'updated_at'}
            if old:
                require(all(new.get(k) == v for k, v in old.items() if k not in allowed), 'unrequested_target_fields_preserved')
            else:
                require(new['id'] not in before[table], 'new_row_identity')
            expected[table][new['id']] = new
        elif task == 3:
            new_rows = [r for pk, r in after['alert_subscriptions'].items() if pk not in before['alert_subscriptions']]
            require(len(new_rows) == 1, 'one_new_alert')
            row = new_rows[0]
            require(row['user_id'] == uid and row['section_slug'] == 'games' and
                    norm(row['keyword']) == 'playstation' and row['frequency'] == 'daily' and row['active'] == 1,
                    'exact_new_alert')
            expected['alert_subscriptions'][row['id']] = row
        elif task == 5:
            row = one(after, 'users', id=uid)
            require(row is not None and norm(row['region']) in ('san francisco, ca', 'san francisco, california') and
                    norm(row['favorite_platform']) == 'nintendo switch 2', 'exact_profile_values')
            expected['users'][uid]['region'] = row['region']
            expected['users'][uid]['favorite_platform'] = row['favorite_platform']
        elif task == 7:
            rows = [r for pk, r in after['comments'].items() if pk not in before['comments']]
            require(len(rows) == 1, 'one_new_comment')
            row = rows[0]
            require(row['user_id'] == uid and row['item_id'] == iid and
                    norm(row['body']).rstrip('.') == 'watch this before the finale', 'exact_posted_comment')
            expected['comments'][row['id']] = row
        elif task == 13:
            row = one(before, 'alert_subscriptions', user_id=uid, section_slug='guides', keyword='weekly update')
            require(row is not None and row['active'] == 1, 'initial_alert_active')
            expected['alert_subscriptions'][row['id']]['active'] = 0
        elif task == 14:
            rows = [r for r in before['saved_items'].values() if r['user_id'] == uid and r['folder'] == 'Deals']
            require(len(rows) == 1, 'one_initial_deals_item')
            del expected['saved_items'][rows[0]['id']]
        elif task == 19:
            import bcrypt
            require(one(before, 'users', email='henry.m@test.com') is None, 'registration_absent_initially')
            new = one(after, 'users', email='henry.m@test.com')
            require(new is not None and new['id'] not in before['users'] and
                    norm(new['username']) == 'henry_m' and norm(new['display_name']) == 'henry m', 'new_registration_identity')
            try:
                password_ok = bcrypt.checkpw(b'TestPass123!', new['password_hash'].encode())
            except (TypeError, ValueError):
                password_ok = False
            require(password_ok, 'requested_registration_password')
            last = trajectory.get('steps', [{}])[-1].get('url', '')
            final = trajectory.get('final_url', last)
            origin = urlsplit(trajectory.get('start_url', ''))
            require(all((urlsplit(u).scheme, urlsplit(u).netloc) == (origin.scheme, origin.netloc) and
                        urlsplit(u).path.rstrip('/') == '/account' for u in (last, final)), 'finished_on_account')
            expected['users'][new['id']] = new
        require(before != after or task in (4, 17), 'state_task_has_delta')
        require(expected == after, 'only_requested_database_changes')
    except (ValueError, KeyError, TypeError, sqlite3.Error, OSError, IndexError) as error:
        j.check('complete_task_contract', False, str(error))
