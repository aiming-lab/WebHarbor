"""Import a browser-saved IMDb webarchive into the HF-managed seed.

Offline, explicit build-time migration; never imported at app startup. Only the
home_features table is changed. Existing catalog and benchmark state stay intact.
Assets are extracted from the archive; --fetch-missing permits fetching exact
image URLs present in its HTML, restricted to IMDb's public media CDN.
"""
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import plistlib
import re
import sqlite3
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import urlopen


class SourcePage(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.in_data = False
        self.data_parts = []
        self.images = []
        self.episodes = []
        self.episode_details = []
        self.episode_detail = None
        self.stack = []
        self.cards = []
        self.card = None
        self.service = ''
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
                       'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append((tag, attrs))
        classes = attrs.get('class', '').split()
        if attrs.get('role') == 'tabpanel' and any(c.startswith('EpisodeRatingCard_card__') for c in classes):
            self.episode_detail = {'depth': len(self.stack), 'image': '', 'info': '',
                                   'plot': '', 'title': '', 'source_path': ''}
        if self.episode_detail:
            if tag == 'img':
                self.episode_detail['image'] = attrs.get('src', '')
            if tag == 'a' and re.match(r'^/title/tt\d+/', attrs.get('href', '')):
                self.episode_detail['source_path'] = attrs['href'].split('?')[0]
        kind = None
        if attrs.get('data-testid') == 'name-born-today-card':
            kind = 'birthday'
        elif 'ipc-poster-card' in classes:
            if 'streaming-picks-title' in classes:
                kind = 'streaming'
            elif any(a.get('data-testid') == 'rttv-parent' for _, a in self.stack):
                kind = 'tv_schedule'
        if kind:
            if self.card:
                raise ValueError('Unexpected nested source card')
            self.card = {'kind': kind, 'depth': len(self.stack), 'heading': '',
                         'rating': '', 'age': '', 'episode': '', 'air_date': '',
                         'image': '', 'source_path': '', 'episode_path': ''}
        if self.card:
            if tag == 'img' and not self.card['image']:
                self.card['image'] = attrs.get('src', '')
            if tag == 'a':
                href = attrs.get('href', '')
                if re.match(r'^/(title/tt|name/nm)\d+/', href) and not self.card['source_path']:
                    self.card['source_path'] = href.split('?')[0]
                if attrs.get('data-testid') == 'rttv-episode-num':
                    self.card['episode_path'] = href.split('?')[0]
        if tag == 'script' and attrs.get('id') == '__NEXT_DATA__':
            self.in_data = True
        if tag == 'img':
            self.images.append(attrs)
        label = attrs.get('aria-label', '')
        episode = re.fullmatch(r'Episode (\d+) of \d+, rated ([\d.]+)/10: (.+)\. Select enter.*', label)
        if attrs.get('role') == 'tab' and episode:
            self.episodes.append({'number': int(episode[1]), 'rating': episode[2], 'title': episode[3]})

    def handle_endtag(self, tag):
        if tag == 'script':
            self.in_data = False
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                if self.episode_detail and index < self.episode_detail['depth']:
                    self.episode_detail.pop('depth')
                    self.episode_details.append(self.episode_detail)
                    self.episode_detail = None
                if self.card and index < self.card['depth']:
                    self.card.pop('depth')
                    self.cards.append(self.card)
                    self.card = None
                del self.stack[index:]
                break

    def handle_data(self, data):
        if self.in_data:
            self.data_parts.append(data)
        if self.episode_detail:
            for _, attrs in reversed(self.stack):
                classes = attrs.get('class', '').split()
                field = next((value for prefix, value in [
                    ('EpisodeRatingCard_plot__', 'plot'), ('EpisodeRatingCard_episodeInfo__', 'info')]
                    if any(c.startswith(prefix) for c in classes)), None)
                if 'ipc-title__text' in classes:
                    field = 'title'
                if field:
                    self.episode_detail[field] += data.strip() + ' '
                    break
        if any(a.get('data-testid') == 'streaming-picks-tab-container' for _, a in self.stack):
            if any(a.get('role') == 'tab' and a.get('aria-selected') == 'true' for _, a in self.stack):
                self.service += data.strip()
        if not self.card:
            return
        fields = {'born-today-name': 'heading', 'born-today-age': 'age',
                  'rttv-episode-num': 'episode', 'rttv-air-date': 'air_date'}
        for _, attrs in reversed(self.stack):
            field = fields.get(attrs.get('data-testid'))
            classes = attrs.get('class', '').split()
            if 'ipc-poster-card__title' in classes:
                field = 'heading'
            elif 'ipc-rating-star--rating' in classes:
                field = 'rating'
            if field:
                self.card[field] += data
                break


def digest(data):
    return hashlib.sha256(data).hexdigest()


def starmeter_entries(props):
    """Use the chart's explicit ranks, never the order of a local catalog."""
    entries, ranks, ids = [], set(), set()
    for edge in props.get('pageData', {}).get('chartNames', {}).get('edges', []):
        node, rank = edge['node'], edge.get('currentRank')
        source_id = node['id']
        if type(rank) is not int or rank < 1 or rank in ranks:
            raise ValueError('Missing, invalid or duplicate STARmeter rank')
        if not re.fullmatch(r'nm\d+', source_id) or source_id in ids:
            raise ValueError('Invalid or duplicate STARmeter name ID')
        ranks.add(rank)
        ids.add(source_id)
        entries.append({
            'source_id': source_id, 'rank': rank, 'heading': node['nameText']['text'],
            'image': (node.get('primaryImage') or {}).get('url', ''),
            'professions': [p['profession']['text'] for p in node.get('professions', [])],
            'known_for': [c['title']['titleText']['text']
                          for c in (node.get('knownForV2') or {}).get('credits', [])],
        })
    return entries


def import_archive(archive_path, database, static, fetch_missing=False):
    archive_bytes = Path(archive_path).read_bytes()
    archive = plistlib.loads(archive_bytes)
    if urlsplit(archive['WebMainResource']['WebResourceURL']).hostname != 'www.imdb.com':
        raise ValueError('Expected an official IMDb browser archive')
    page = SourcePage(archive['WebMainResource']['WebResourceData'].decode('utf-8'))
    props = json.loads(''.join(page.data_parts))['props']['pageProps']
    captured = props['requestContext']['timestamp']
    resources = {r['WebResourceURL']: r for r in archive.get('WebSubresources', [])}
    manifest = []
    static = Path(static)
    downloaded = {}

    def image(source):
        if not source:
            return ''
        prefix = source.split('._')[0]
        candidates = [r for url, r in resources.items()
                      if url.split('._')[0] == prefix and r['WebResourceMIMEType'].startswith('image/')]
        if candidates:
            resource = max(candidates, key=lambda r: len(r['WebResourceData']))
            url, data = resource['WebResourceURL'], resource['WebResourceData']
        else:
            matches = [img for img in page.images if img.get('src', '').split('._')[0] == prefix]
            if not fetch_missing:
                raise ValueError('Image not saved in archive: ' + source)
            img = matches[0] if matches else {'src': source}
            # srcset commas also occur inside IMDb crop parameters. Width
            # descriptors delimit entries; splitting on every comma is invalid.
            urls = re.findall(r'(https://\S+) \d+w', img.get('srcset', ''))
            url = urls[-1] if urls else img['src']
            if urlsplit(url).hostname != 'm.media-amazon.com':
                raise ValueError('Unexpected media host')
            cache = static.parent / 'scraped_data/homepage-media' / digest(url.encode())
            if cache.exists():
                data = cache.read_bytes()
            elif url in downloaded:
                data = downloaded[url]
            else:
                for attempt in range(2):
                    try:
                        with urlopen(url, timeout=30) as response:
                            if not response.headers.get('Content-Type', '').startswith('image/'):
                                raise ValueError('Expected an image')
                            data = response.read(8_000_001)
                        break
                    except URLError as exc:
                        if attempt:
                            raise ValueError('Could not retrieve source image: ' + url) from exc
                if len(data) <= 8_000_000 and data.startswith((b'\xff\xd8\xff', b'\x89PNG')):
                    cache.parent.mkdir(parents=True, exist_ok=True)
                    cache.write_bytes(data)
                    downloaded[url] = data
            if len(data) > 8_000_000:
                raise ValueError('Image exceeds import budget')
        if not data.startswith((b'\xff\xd8\xff', b'\x89PNG')):
            raise ValueError('Expected a JPEG or PNG')
        filename = 'images/home/' + digest(data)[:24] + ('.png' if data.startswith(b'\x89PNG') else '.jpg')
        destination = static / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.read_bytes() != data:
            raise ValueError('Asset path collision')
        if not destination.exists():
            destination.write_bytes(data)
        manifest.append({'path': filename, 'source_url': url, 'sha256': digest(data), 'bytes': len(data)})
        return filename

    rows = []
    for key, placement in props.get('cmsContext', {}).get('transformedPlacements', {}).items():
        args = placement.get('transformedArguments', {})
        if key.startswith('hero-video-'):
            payload = {'title_id': args['titleId'], 'title': args['titleText'],
                       'duration': args['runtime'], 'source_cta': args['subHeadline']}
            rows.append((key, 'hero', int(key.rsplit('-', 1)[1]), args['headline'],
                         'Trailer preview', image(args['videoSlateImage']['url']),
                         image(args['posterImage']['url']), 'https://www.imdb.com/video/' + args['videoId'] + '/',
                         captured, json.dumps(payload)))
        elif key.startswith('featured-today-'):
            rows.append((key, 'editorial', int(key.rsplit('-', 1)[1]), args['displayTitle'],
                         args.get('description', ''), image(args['linkedImages'][0]['imageModel']['url']),
                         '', 'https://www.imdb.com' + args['linkTargetUrl'], captured,
                         json.dumps({'source_cta': args.get('callToActionText', ''), 'type': args.get('iconName', '')})))
        elif key.startswith('pill-'):
            rows.append((key, 'topic', int(key.rsplit('-', 1)[1]), args['displayTitle'], '', '', '',
                         'https://www.imdb.com' + args['linkTargetUrl'], captured, '{}'))
        elif key == 'center-1':
            spec = json.loads(args['json'])
            title = args['transformedJson']
            episodes = []
            for episode in page.episodes:
                detail = next((d for d in page.episode_details
                               if re.match(r'S\d+\.E' + str(episode['number']) + r'\s', d['info'])), None)
                enriched = dict(episode)
                if detail:
                    if detail['title'].strip() != episode['title']:
                        raise ValueError('Episode label and detail title disagree')
                    enriched.update(info=detail['info'].strip(), plot=detail['plot'].strip(),
                                    image_path=image(detail['image']),
                                    source_url='https://www.imdb.com' + detail['source_path'])
                episodes.append(enriched)
            rows.append((key, 'spotlight', 1, spec['title'], spec['description'],
                         '', image(title['primaryImage']['url']),
                         'https://www.imdb.com/title/' + title['id'] + '/episodes/', captured,
                         json.dumps({'title_id': title['id'], 'title': title['titleText']['text'],
                                     'season': title['episodes']['episodes']['edges'][0]['node']['series']['displayableEpisodeNumber']['displayableSeason']['season'],
                                     'episodes': episodes,
                                     'credits': [{'role': c['category']['text'], 'names': [
                                         n['name']['nameText']['text'] for n in c['credits']]}
                                         for c in title['principalCredits']]})))
    # Keep the benchmark news table untouched; this snapshot has its own links.
    for position, edge in enumerate(props.get('pageQueryData', {}).get('data', {}).get('news', {}).get('edges', [])):
        item = edge['node']
        rows.append((item['id'], 'news', position, item['articleTitle']['plainText'],
                     item['text']['plainText'], image(item['image']['url']), '', 'https://www.imdb.com/news/' + item['id'] + '/',
                     captured, json.dumps({'date': item['date'], 'source': item['source']['homepage']['label']})))
    for entry in starmeter_entries(props):
        payload = {key: value for key, value in entry.items() if key not in {'heading', 'image'}}
        rows.append(('starmeter-' + entry['source_id'], 'starmeter', entry['rank'],
                     entry['heading'], ' · '.join(entry['professions']), image(entry['image']), '',
                     'https://www.imdb.com/name/' + entry['source_id'] + '/', captured, json.dumps(payload)))
    positions = {}
    for card in page.cards:
        kind = card['kind']
        if not card['heading'].strip() or not card['source_path'] or not card['image']:
            raise ValueError('Incomplete loaded homepage card: ' + str(card))
        if kind == 'streaming' and not page.service:
            raise ValueError('Streaming cards require an observed selected service')
        positions[kind] = positions.get(kind, 0) + 1
        source_id = card['source_path'].strip('/').split('/')[-1]
        payload = {k: v.strip() for k, v in card.items()
                   if k not in {'kind', 'heading', 'image', 'source_path'} and v}
        payload['source_id'] = source_id
        if kind == 'streaming':
            payload['service'] = page.service
        subtitle = {'birthday': 'Born on ' + captured[5:10],
                    'streaming': page.service + ' · availability at capture',
                    'tv_schedule': ' · '.join(filter(None, [card['episode'], card['air_date']]))}[kind]
        rows.append((kind + '-' + source_id, kind, positions[kind], card['heading'].strip(),
                     subtitle, image(card['image']) if kind == 'birthday' else '',
                     image(card['image']) if kind != 'birthday' else '',
                     'https://www.imdb.com' + card['source_path'], captured, json.dumps(payload)))
    if not rows:
        raise ValueError('No supported source content found')
    columns = 'id,kind,position,heading,subtitle,image_path,poster_path,source_url,captured_at,payload'
    with sqlite3.connect(database) as con:
        before = {name: con.execute('SELECT * FROM "' + name + '" ORDER BY rowid').fetchall()
                  for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name!='home_features'")}
        con.execute("""CREATE TABLE IF NOT EXISTS home_features (
            id VARCHAR(80) PRIMARY KEY, kind VARCHAR(30) NOT NULL, position INTEGER NOT NULL,
            heading TEXT NOT NULL, subtitle TEXT, image_path TEXT, poster_path TEXT,
            source_url TEXT NOT NULL, captured_at VARCHAR(40) NOT NULL, payload JSON NOT NULL)""")
        # An archive saved before lazy loading must not erase previously sourced
        # lower-page collections. Replace only the kinds actually present here.
        kinds = sorted({row[1] for row in rows})
        placeholders = ','.join('?' for _ in kinds)
        current = con.execute('SELECT ' + columns + ' FROM home_features WHERE kind IN ('
                              + placeholders + ') ORDER BY id', kinds).fetchall()
        if current != sorted(rows):
            con.execute('DELETE FROM home_features WHERE kind IN (' + placeholders + ')', kinds)
            con.executemany('INSERT INTO home_features (' + columns + ') VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
        for name, values in before.items():
            if values != con.execute('SELECT * FROM "' + name + '" ORDER BY rowid').fetchall():
                raise ValueError('Protected table changed: ' + name)
    return {'archive_sha256': digest(archive_bytes), 'captured_at': captured, 'features': len(rows),
            'assets': manifest, 'protected_tables_unchanged': list(before),
            'seed_sha256': digest(Path(database).read_bytes())}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('database', type=Path)
    parser.add_argument('static', type=Path)
    parser.add_argument('--fetch-missing', action='store_true')
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    result = import_archive(args.archive, args.database, args.static, args.fetch_missing)
    args.manifest.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'assets'}, indent=2))
