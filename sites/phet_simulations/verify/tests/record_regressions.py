#!/usr/bin/env python3
"""Record scripted browser regressions, NOT independent agent exploration.

Run with Flask dependencies + playwright, using --output outside the source tree.
Screenshots include the viewport AFTER explicit scroll; full-page is supplementary.
Every task gets a fresh browser context and frozen before/after SQLite snapshots.
"""
import argparse
import hashlib
import importlib.util
import json
import logging
from pathlib import Path
import shutil
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright, expect
from werkzeug.serving import make_server

SITE = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--chrome', default=None)
    parser.add_argument('--start-task', type=int, default=0)
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='phet-ui-') as temp, sync_playwright() as pw:
        root = Path(temp)
        for name in ['app.py', 'catalog_data.py', '_health.py']:
            shutil.copy2(SITE / name, root / name)
        shutil.copytree(SITE / 'templates', root / 'templates')
        (root / 'static').symlink_to(SITE / 'static', target_is_directory=True)
        (root / 'instance').mkdir()
        seed = SITE / 'instance_seed/phet_simulations.db'
        assert seed.exists(), 'Fetch the pinned PhET assets first'
        live = root / 'instance/phet_simulations.db'
        shutil.copy2(seed, live)
        sys.path.insert(0, str(root))
        spec = importlib.util.spec_from_file_location('app', root / 'app.py')
        mod = importlib.util.module_from_spec(spec); sys.modules['app'] = mod; spec.loader.exec_module(mod)
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        server = make_server('127.0.0.1', 0, mod.app, threaded=False)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = f'http://127.0.0.1:{server.server_port}'
        browser = pw.chromium.launch(executable_path=args.chrome, headless=True)
        tasks = [json.loads(line) for line in (SITE / 'tasks.jsonl').read_text().splitlines()]
        answers = [
            'Color Vision; Density; Natural Selection.',
            'Build an Atom: version 1.9.3, 104 languages.',
            'Natural Selection: Elementary School, Middle School, High School; not university.',
            '5 simulations in the New set were released in 2025.',
            'Build an Atom is the most translated, with 104 languages.',
            'Quantum Wave Interference: released 2026-09-10; Physics and Chemistry.',
            'Arabic: 119 simulations.',
            'Arabic (Morocco): 103 simulations.',
            'The quantum search has 7 results. Quantum Wave Interference is version 1.0.0.',
            'Heat & Thermo: 9 simulations.',
            'Least-Squares Regression; Projectile Data Lab; Projectile Sampling Distributions; Quantum Measurement; Quantum Coin Toss.',
            '49 simulations are available in PhET Studio.',
            'The teacher account has 4 saved simulations.',
            'Saved Membrane Transport with a note to the student account.',
            'Created test_user@phet.test as a teacher and saved Number Pairs.',
            'Equivalent Fractions Game: 50 minutes.',
            '120 simulations, 5 subjects, 132 languages, 14 activities.',
            'Build an Atom has more languages: 104 versus 31 for Membrane Transport, a difference of 73.',
        ]
        try:
            for n, task in enumerate(tasks):
                if n < args.start_task: continue
                with mod.app.app_context():
                    mod.db.session.remove(); mod.db.engine.dispose()
                shutil.copy2(seed, live)
                run = output / f'task_{n}'; shots = run / 'screenshots'; shots.mkdir(parents=True, exist_ok=True)
                shutil.copy2(live, run / 'initial.db')
                context = browser.new_context(viewport={'width':1440,'height':900})
                page = context.new_page(); steps = []
                def record(action, selector=None):
                    if selector:
                        target = page.locator(selector).first
                        target.scroll_into_view_if_needed()
                    page.wait_for_load_state('networkidle')
                    index = len(steps)
                    shot = f'step_{index:03d}.png'
                    page.screenshot(path=str(shots / shot))
                    page.screenshot(path=str(shots / shot.replace('.png','-full.png')), full_page=True)
                    steps.append({'url':page.url,'action':action,'screenshot_after':f'screenshots/{shot}'})
                def visit(path):
                    response = page.goto(base+path)
                    assert response.status == 200, (path,response.status)
                    record({'type':'goto','path':path})
                def detail(path):
                    visit(path)
                    record({'type':'scroll','target':'Sim details'}, '.side-card:has(h3:text-is("Sim details"))')
                    if page.locator('.sim-detail-section:has(h2:text-is("Related Sims"))').count():
                        record({'type':'scroll','target':'Related Sims'}, '.sim-detail-section:has(h2:text-is("Related Sims"))')
                def all_cards():
                    return list(dict.fromkeys(page.locator('.sim-title a').evaluate_all('(els)=>els.map(e=>e.getAttribute("href"))')))
                def login(who):
                    visit('/login'); page.locator('[name=email]').fill(who+'@phet.test')
                    page.locator('[name=password]').fill('phet-'+who+'-pass')
                    page.locator('.auth-card form button[type=submit]').click(); expect(page).to_have_url(base+'/account')
                    record({'type':'submit','form':'login','account':who+'@phet.test'})
                if n == 0:
                    visit('/simulations'); page.locator('[name=subject][value=biology]').check(); page.locator('[name=grade][value=elementary]').check()
                    page.locator('button[type=submit].filter-clear').click(); record({'type':'filter','subject':'biology','grade':'elementary'},'.results-count')
                    assert {t.strip() for t in page.locator('.sim-title').all_text_contents()} == {'Color Vision','Density','Natural Selection'}
                elif n in (1,17):
                    detail('/simulation/build-an-atom')
                    assert '1.9.3' in page.inner_text('body') and '104 languages' in page.inner_text('body')
                    if n==17: detail('/simulation/membrane-transport'); assert '31 languages' in page.inner_text('body')
                elif n in (2,3,8):
                    if n==3:
                        visit('/simulations')
                        page.locator('summary').filter(has_text='Release Type').click()
                        page.locator('[name=release][value=new]').check()
                        page.locator('button[type=submit].filter-clear').click()
                        record({'type':'filter','release':'new'},'.results-count')
                    elif n==8:
                        visit('/')
                        page.locator('.search-form').hover()
                        page.locator('.search-form input[name=q]').fill('quantum')
                        page.locator('.search-form button').click()
                        record({'type':'search','query':'quantum'})
                    else:
                        visit('/simulations?subject=biology')
                    paths = all_cards()
                    assert len(paths)=={2:8,3:12,8:7}[n]
                    for path in paths: detail(path)
                elif n in (4,5):
                    visit('/simulations')
                    page.locator('.results-sort select').select_option(label='Most translated' if n==4 else 'Newest')
                    record({'type':'sort','by':'translations' if n==4 else 'newest'})
                    path = all_cards()[0]; assert path.endswith('build-an-atom' if n==4 else 'quantum-wave-interference')
                    detail(path)
                elif n in (6,7):
                    visit('/translations'); code='ar' if n==6 else 'ar_MA'
                    selector=f'.language-card:has(a[href="/translations/{code}"])'
                    record({'type':'scroll','target':code},selector)
                    assert str(119 if n==6 else 103)+' simulations' in page.locator(selector).inner_text()
                elif n==9:
                    visit('/simulations'); page.locator('[name=topic][value=heat-and-thermo]').check();page.locator('button[type=submit].filter-clear').click();record({'type':'filter','topic':'heat-and-thermo'},'.results-count');assert '9 results' in page.inner_text('body')
                elif n==10: detail('/simulation/plinko-probability')
                elif n==11:
                    visit('/simulations');page.locator('.browse-subtab').filter(has_text='Customize').click();record({'type':'click','tab':'Customize'});assert len(all_cards())==49
                elif n==12:
                    login('teacher');assert page.locator('.saved-item').count()==4
                elif n==13:
                    login('student');detail('/simulation/membrane-transport')
                    page.locator('#save-note').fill('Use for the membrane transport lesson.')
                    record({'type':'fill','field':'notes'},'.save-form')
                    page.locator('button[data-action=save]').click();expect(page.locator('.save-status')).to_have_text('Saved to your account.')
                    record({'type':'click','button':'Save to my account'},'.save-form')
                elif n==14:
                    visit('/register');page.locator('[name=name]').fill('Review Teacher');page.locator('[name=email]').fill('test_user@phet.test');page.locator('[name=password]').fill('review-password-123')
                    page.locator('.auth-card form button[type=submit]').click();expect(page).to_have_url(base+'/account');record({'type':'submit','form':'register','email':'test_user@phet.test'})
                    detail('/simulation/number-pairs');page.locator('button[data-action=save]').click();expect(page.locator('.save-status')).to_have_text('Saved to your account.');record({'type':'click','button':'Save to my account'},'.save-form')
                elif n==15:
                    visit('/teachers/activities');page.select_option('[name=grade]','elementary');page.locator('.filter-bar button').click();record({'type':'filter','grade':'elementary'},'.activity-grid');assert 'Equivalent Fractions Game' in page.inner_text('body') and '50 min' in page.inner_text('body')
                elif n==16: visit('/about');record({'type':'scroll','target':'By the numbers'},'.stats-grid')
                context.close()
                shutil.copy2(live, run/'after.db')
                if n not in (13,14): assert (run/'initial.db').read_bytes()==(run/'after.db').read_bytes()
                trajectory=dict(task, steps=steps, final_answer=answers[n],run_kind='scripted_regression',model='no-model',environment={'site_port':40035,'recorded_origin':base},capture_policy='Viewport after explicit scroll is primary; full-page screenshots are supplementary. Expected answers are test fixtures, not independent agent output.')
                (run/'trajectory.json').write_text(json.dumps(trajectory,indent=2))
                print(f'task {n}: UI recorded',flush=True)
            # Responsive sweep + actual mobile navigation interaction.
            context=browser.new_context();page=context.new_page();layout=[]
            paths=['/','/simulations','/simulations?view=browse','/simulations?view=customize','/simulations?subject=biology&grade=elementary','/simulation/build-an-atom','/simulation/membrane-transport','/simulation/quantum-wave-interference','/search?q=quantum','/translations','/translations/ar','/translations/ar_MA','/teachers','/teachers/activities','/teachers/activity/1','/about','/accessibility','/login','/register','/simulations?topic=heat-and-thermo','/simulations?subject=physics&topic=electricity-magnets-and-circuits&grade=high&language=en&release=updated']
            for width in [1440,768,390]:
                page.set_viewport_size({'width':width,'height':900})
                for path in paths:
                    page.goto(base+path);page.wait_for_load_state('networkidle')
                    dims=page.evaluate('({width:innerWidth, document:document.documentElement.scrollWidth})')
                    layout.append({'path':path,**dims});assert dims['document']<=dims['width'],(path,dims)
                page.goto(base+'/');page.screenshot(path=str(output/f'home-{width}.png'),full_page=True)
            page.locator('#nav-toggle').click();expect(page.locator('#nav-toggle')).to_have_attribute('aria-expanded','true')
            (output/'responsive.json').write_text(json.dumps(layout,indent=2));context.close()
        finally:
            browser.close();server.shutdown();thread.join()
        manifest={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest() for p in output.rglob('*') if p.is_file() and p.name!='manifest.json'}
        (output/'manifest.json').write_text(json.dumps(manifest,indent=2))


if __name__=='__main__': main()
