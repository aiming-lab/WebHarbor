"""Scrape all ohio.gov resource detail pages (server-rendered) into structured JSON."""
import httpx, json, re, html as H, pathlib, sys
from concurrent.futures import ThreadPoolExecutor, as_completed

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
OUT = pathlib.Path(__file__).resolve().parent.parent / 'scraped_data'
OUT.mkdir(exist_ok=True)

def strip_tags(s):
    s = re.sub(r'<[^>]+>', ' ', s)
    return re.sub(r'\s+', ' ', H.unescape(s)).strip()

def parse_resource(src):
    d = {}
    m = re.search(r'<h1 class="odx-content__title">\s*(.*?)\s*</h1>', src, re.S)
    d['title'] = strip_tags(m.group(1)) if m else None
    m = re.search(r'<div class="odx-content__summary">\s*(.*?)\s*</div>', src, re.S)
    d['summary'] = strip_tags(m.group(1)) if m else None
    m = re.search(r'<section id="js-odx-content__body" class="odx-content__body">(.*?)</section>', src, re.S)
    if m:
        body = m.group(1)
        # paragraphs as list of html strings
        paras = re.findall(r'<p[^>]*>(.*?)</p>', body, re.S)
        d['body_html'] = paras
        d['body_links'] = re.findall(r'<a href="([^"]+)"[^>]*>(.*?)</a>', body, re.S)
        d['body_text'] = strip_tags(body)
    m = re.search(r'odx-external-link__button[^"]*"[^>]*href="([^"]+)"', src)
    d['launch_url'] = m.group(1) if m else None
    m = re.search(r'odx-resource-details__detail--publish-date.*?odx-resource-details__value">([^<]+)<', src, re.S)
    d['published'] = strip_tags(m.group(1)) if m else None
    # related agencies
    rel = re.findall(r'<article class="odx-related-agencies__container">(.*?)</article>', src, re.S)
    d['related_agencies'] = []
    for r0 in rel:
        m2 = re.search(r'odx-related-agencies__name[^>]*>(.*?)<', r0, re.S)
        m3 = re.search(r'href="([^"]+)"[^>]*class="[^"]*odx-related-agencies__link', r3 if False else r0)
        if m3 is None:
            m3 = re.search(r'<a[^>]*href="([^"]+)"', r0)
        name = strip_tags(m2.group(1)) if m2 else None
        href = m3.group(1) if m3 else None
        if name:
            d['related_agencies'].append({'name': name, 'href': href})
    # hero image if any
    m = re.search(r'<img[^>]+src="([^"]+)"[^>]*class="[^"]*odx-content__image', src)
    if not m:
        m = re.search(r'class="[^"]*odx-content__image[^"]*"[^>]*src="([^"]+)"', src)
    d['image'] = m.group(1) if m else None
    return d

def fetch(url):
    try:
        with httpx.Client(follow_redirects=True, timeout=40, headers={'User-Agent': UA, 'Accept-Language': 'en-US,en;q=0.9'}) as cx:
            r = cx.get(url)
            return url, r.status_code, r.text
    except Exception as e:
        return url, -1, str(e)

def main():
    results = json.load(open('/tmp/ohio_recon/search_results.json'))
    print('resources from search:', len(results))
    out = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.fetch if False else ex.submit(fetch, r['link']): r for r in results}
        done = 0
        for fut in as_completed(futs):
            url, code, src = fut.result()
            r = futs[fut]
            if code == 200:
                d = parse_resource(src)
                d.update({'url': url, 'search_summary': r.get('summary'), 'search_date': r.get('date')})
                out.append(d)
            else:
                out.append({'url': url, 'error': code})
            done += 1
            if done % 50 == 0:
                print(f'{done}/{len(results)}')
    (OUT / 'resources_raw.json').write_text(json.dumps(out, indent=1))
    ok = [o for o in out if o.get('title')]
    print('parsed ok:', len(ok), '/', len(out))

if __name__ == '__main__':
    main()
