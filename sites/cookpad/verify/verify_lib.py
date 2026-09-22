#!/usr/bin/env python3
"""Snapshot-only deterministic grading, with bounded natural-answer parsing.

Not a general language-understanding system. See README for supported wording
and regression controls. Expectations live only in reviewer-owned files.
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import sys
import unicodedata
from urllib.parse import urlsplit, parse_qs

SITE = Path(__file__).resolve().parents[1]
CONTRACTS = json.loads(Path(__file__).with_name('contracts.json').read_text())
TASK_COUNT = len(CONTRACTS)
STATEFUL_TASKS = {c['index'] for c in CONTRACTS if c['state']}
ALIASES = {
    24769889: ['Japanese-Inspired Veggie Pizza'],
    25112278: ['Zoe Krill’s cous cous miso soup', 'Miso want cous cous'],
    26394567: ['Crispy salt and pepper tofu', 'air-fryer salt and pepper tofu'],
    26289796: ['Traditional Mapo Tofu plant-based', 'plant-based Mapo Tofu'],
    25038367: ['Chicken Teriyaki'],
    25797934: ['Marx Meal Prep Stir-Fry'],
}

def norm(value):
    value = str(value).replace('⅓', ' 1/3').replace('⁄', '/')
    value = unicodedata.normalize('NFKC', str(value)).casefold().replace('&', ' and ')
    value = re.sub(r"['’]", '', value)
    return re.sub(r'[^\w/.\s]', ' ', value).strip()

def plain(value):
    return re.sub(r'\s+', ' ', norm(value))

def database(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('missing saved database: ' + str(path))
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        conn.row_factory = sqlite3.Row
        schema = sorted(tuple(r) for r in conn.execute(
            "SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"))
        tables = {}
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            name = row[0]
            quoted = '"' + name.replace('"', '""') + '"'
            tables[name] = [dict(r) for r in conn.execute('SELECT * FROM ' + quoted + ' ORDER BY id')]
        return schema, tables

def recipes():
    return {r['id']: r for r in database(SITE/'instance_seed/cookpad.db')[1]['recipe']}

def step_urls(traj):
    origin = urlsplit(traj.get('start_url', ''))
    return [urlsplit(str(s.get(k, ''))) for s in traj.get('steps', []) for k in ('url','url_after')
            if s.get(k) and urlsplit(str(s[k])).netloc == origin.netloc
            and urlsplit(str(s[k])).scheme == origin.scheme]

def navigation_ok(c, traj):
    urls = step_urls(traj)
    paths = {u.path.rstrip('/') or '/' for u in urls}
    # Details are useful for read facts and explicitly comparing recipes, not
    # mandatory extra clicks for importing ingredients or editing an existing note.
    if c['facts'] and not all('/recipe/cookpad-'+str(i) in paths for i in c['recipes']):
        return False
    nav = c['navigation']
    if nav and ':' in nav:
        kind, token = nav.split(':', 1)
        route = '/help' if kind == 'help' else '/search'
        allowed = {route} if kind == 'help' else {'/search','/recipes','/all-recipes'}
        if not any(u.path in allowed and token in plain(parse_qs(u.query).get('q',[''])[0]).split() for u in urls):
            return False
        if kind == 'help':
            article = '/help/shopping-list-overview' if c['index'] == 10 else '/help/saving-recipes'
            if article not in paths:
                return False
    elif nav and nav not in paths and not (nav == '/recipe-box' and '/favorites' in paths):
        return False
    if c['index'] == 5 and not any(u.path == '/category/desserts' and parse_qs(u.query).get('max_time') == ['15'] for u in urls):
        return False
    if c['state']:
        needed = {'list_new':'/shopping-list', 'list_edit':'/shopping-list',
                  'meal':'/meal-plan', 'note':'/recipe-box'}[c['state']['kind']]
        if needed not in paths and not (needed == '/recipe-box' and '/favorites' in paths):
            return False
    return True

def entity_sections(answer, ids, catalog):
    """Associate each paragraph/clause/table row with its named recipe.

    Full titles and documented distinctive short titles are recognized. A
    one-entity line can put values before its title; multi-entity lines are
    divided at mentions. Markdown headers supply units to table cells.
    """
    aliases = {i: sorted({plain(catalog[i]['title']), *map(plain, ALIASES.get(i, []))}, key=len, reverse=True) for i in ids}
    result = {i: [] for i in ids}
    headers = None
    active = None
    for line in answer.splitlines():
        if '|' in line:
            cells = [cell.strip() for cell in line.strip().strip('|').split('|')]
            if any(re.search(r'\b(time|minutes|saves|author)\b', cell, re.I) for cell in cells) and not any(
                    alias in plain(line) for group in aliases.values() for alias in group):
                headers = cells
                continue
            if headers and len(headers) == len(cells):
                parts = []
                for h, cell in zip(headers, cells):
                    if plain(h) in {'saves', 'bookmarks'}:
                        parts.append(cell + ' saves')
                    elif plain(h) in {'time minutes', 'cooking time minutes'}:
                        parts.append(cell + ' minutes')
                    else:
                        parts.append(f'{h}: {cell}')
                line = '; '.join(parts)
        text = plain(line)
        found = []
        for i, variants in aliases.items():
            for alias in variants:
                matches = list(re.finditer(r'(?<!\w)'+re.escape(alias)+r'(?!\w)', text))
                if matches:
                    found.extend((m.start(),m.end(),i) for m in matches)
                    break
        found.sort()
        if not found:
            if active is not None:
                result[active].append(text)
            continue
        if len({i for _,_,i in found}) == 1:
            active = found[0][2]
            result[found[0][2]].append(text)
        else:
            active = None
            for n,(start,end,i) in enumerate(found):
                result[i].append(text[start:found[n+1][0] if n+1<len(found) else len(text)])
    return {i: ' '.join(parts) for i,parts in result.items()}

def numbers(text):
    text = text.replace(',', '')
    for word, value in {'one':1,'two':2,'three':3,'four':4,'five':5,'six':6,'ten':10,'fourteen':14,
                        'fifteen':15,'twenty':20,'thirty':30,'forty-five':45,'sixty':60}.items():
        text = re.sub(r'\b'+word+r'\b', str(value), text)
    text = re.sub(r'\ban? (hour|minute)\b', r'1 \1', text)
    return text

def durations(text):
    text = numbers(text)
    values = []
    compound = r'(\d+(?:\.\d+)?)\s*(?:hours?|hrs?|h)\s*(?:and\s*)?(\d+(?:\.\d+)?)\s*(?:minutes?|mins?|m)\b'
    values.extend(float(h)*60+float(m) for h,m in re.findall(compound,text))
    text = re.sub(compound, '', text)
    pattern = r'(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?)\b'
    for m in re.finditer(pattern, text):
        # A comparison difference is graded separately, not an extra cook time.
        if re.match(r'\s*(?:longer|shorter|faster|slower|more|less)\b', text[m.end():]):
            continue
        unit=m[2]
        values.append(float(m[1]) * (60 if unit.startswith('h') else 1/60 if unit.startswith('s') else 1))
    # Tables with explicit header units.
    values += [float(v) for v in re.findall(r'time minutes\s+(\d+(?:\.\d+)?)\b',text)]
    return values

def count_values(text):
    text = numbers(text)
    # Original formatting with thousands separators was stripped before norm.
    pairs = re.findall(r'\b(\d+)\s*(?:saves?|bookmarks?)\b|\b(?:saves?|bookmarks?)\s+(?:is\s+|are\s+)?(\d+)\b', text)
    return [int(a or b) for a,b in pairs]

def answer_ok(index, answer, catalog=None):
    c=CONTRACTS[index]
    if not answer.strip():
        return False
    if not c['facts']:
        # State is authoritative; do not mandate a particular success sentence.
        return True
    catalog = catalog or recipes()
    answer = re.sub(r'(?<=\d),(?=\d{3}\b)', '', answer)
    sections=entity_sections(answer,c['recipes'],catalog)
    for rid in c['recipes']:
        r=catalog[rid]; section=sections[rid]
        if not section:
            return False
        # Reject negated assertions, while permitting truthful unknown values and
        # exclusions such as "not reviews". Recipe names containing "no" survive.
        facts = section
        for title in [r['title'], *ALIASES.get(rid,[])]:
            facts = facts.replace(plain(title), '')
        facts = re.sub(r'(?:not (?:provided|supplied|listed|specified|available|reviews|ratings)|no (?:time|cooking time)(?: is)? (?:provided|supplied|listed))', '', facts)
        if re.search(r'\b(?:not|never|isnt|isn t|doesnt|doesn t|incorrect|wrong|false)\b', facts):
            return False
        for fact in c['facts']:
            if fact=='time':
                expected=r['total_time_mins']; values=durations(section)
                if expected is None:
                    if values or not re.search(r'(?:time.*?(?:unknown|not (?:provided|supplied|listed|specified|available))|(?:unknown|unspecified).*?time)',section):
                        return False
                elif not values or any(abs(v-expected)>0.02 for v in values):
                    return False
            elif fact=='saves':
                counts = count_values(section)
                if not counts or any(v != r['save_count'] for v in counts):
                    return False
            elif fact=='author':
                if plain(r['author_name']) not in section:
                    return False
                for marker in re.finditer(r'\b(?:by|author(?: is)?)\s+', section):
                    if not section[marker.end():].startswith(plain(r['author_name'])):
                        return False
                # A second named catalogue author contradicts this attribution.
                other={plain(x['author_name']) for x in catalog.values()}-{plain(r['author_name'])}
                if any(re.search(r'\b(?:by|author)\s+'+re.escape(a)+r'\b',section) for a in other):
                    return False
            elif fact=='tofu':
                values=[float(a)*(1000 if b.startswith('k') else 1) for a,b in re.findall(r'(\d+(?:\.\d+)?)\s*(kg|kilograms?|g|grams?)\s+(?:of\s+)?(?:firm\s+|organic\s+|medium soft\s+)*tofu',section)]
                if values != [220 if rid==26394567 else 500]:
                    return False
            elif fact=='sugar':
                quantities = re.findall(r'(?<![\d/.])(\d+(?:\.\d+)?(?:\s+(?:and\s+)?\d+/\d+)?)\s*cups?\s+(?:of\s+)?sugar', numbers(section))
                def cups(value):
                    return sum(float(part.split('/')[0])/float(part.split('/')[1]) if '/' in part else float(part) for part in value.replace('and','').split())
                expected = 4/3 if rid==367685 else 1
                if not quantities or any(abs(cups(q)-expected)>0.005 for q in quantities):
                    return False
            elif fact=='eggs':
                if re.findall(r'\b(\d+)\s+(?:large\s+)?eggs?\b',numbers(section)) != ['2']:
                    return False
            elif fact=='slot':
                slot = 'monday breakfast' if rid==26400824 else 'sunday dinner'
                if slot not in section:
                    return False
    if c.get('difference'):
        # Bind the direction to lasagna, not just number overlap.
        text=plain(answer)
        if not re.search(r'\blasagna\b[^.\n]{0,100}\b41\s+(?:minutes?|mins?)\s+longer', text):
            return False
        if re.search(r'\blasagna\b[^.\n]{0,90}\b(?:shorter|faster)\b|\bcookies\b[^.\n]{0,90}\b(?:longer|slower)\b',text):
            return False
    return True

def state_ok(c, before_path, after_path):
    before_schema,before=database(before_path)
    after_schema,after=database(after_path)
    fixture_schema,fixture=database(SITE/'instance_seed/cookpad.db')
    if before_schema != fixture_schema or before != fixture:
        return False,'initial snapshot is not the reviewed reset fixture'
    if before_schema != after_schema:
        return False,'database schema changed'
    state=c['state']
    if not state:
        return (before==after,'read-only database preserved')
    kind=state['kind']; uid=state['user']
    table={'list_new':'shopping_list','list_edit':'shopping_list','meal':'meal_plan_item','note':'recipe_box_item'}[kind]
    for name in before:
        if name!=table and before[name]!=after[name]:
            return False,'unrequested changes to '+name
    old={r['id']:r for r in before[table]}; new={r['id']:r for r in after[table]}
    if kind=='list_new':
        added=set(new)-set(old)
        if len(added)!=1 or any(new.get(i)!=r for i,r in old.items()):
            return False,'expected one new list and all previous rows unchanged'
        row=new[added.pop()]
        recipe=next(r for r in before['recipe'] if r['id']==state['recipe'])
        wanted=list(dict.fromkeys(json.loads(recipe['ingredients_json'])))
        if state.get('add'):
            wanted.append(state['add'])
        ok=(row['user_id']==uid and row['name']==state['name'] and json.loads(row['items_json'])==wanted)
        return ok,'exact new list owner, name and ingredients'
    if kind in {'list_edit','note'}:
        targets=[r for r in old.values() if r['user_id']==uid and (
            r.get('name')==state.get('name') if kind=='list_edit' else r.get('recipe_id')==state['recipe'])]
        if len(targets)!=1:
            return False,'expected one seeded target'
        target=targets[0]; desired=dict(target)
        if kind=='list_edit':
            items=json.loads(target['items_json']);items.remove(state['remove']);items.append(state['add'])
            desired['items_json']=json.dumps(items)
        else:
            desired['notes']=state['note']
        if kind=='list_edit' and target['id'] in new:
            # Whitespace differences in JSON serialization are immaterial.
            new[target['id']]=dict(new[target['id']],items_json=json.dumps(json.loads(new[target['id']]['items_json'])))
        expected=dict(old);expected[target['id']]=desired
        return new==expected,'only requested list items or note changed'
    if kind=='meal':
        slot=lambda r:r['user_id']==uid and r['day']==state['day'] and r['meal_type']==state['meal']
        old_slot={i for i,r in old.items() if slot(r)}
        new_slot={i for i,r in new.items() if slot(r)}
        if len(new_slot)!=1:
            return False,'expected exactly one target meal'
        row=new[next(iter(new_slot))]
        ok=row['recipe_id']==state['recipe'] and {i:r for i,r in old.items() if i not in old_slot}=={i:r for i,r in new.items() if i not in new_slot}
        return ok,'only requested meal slot changed'
    return False,'unknown state contract'

def evaluate(task_index, traj, initial_db='', after_db='', container=None):
    checks=[]
    try:
        c=CONTRACTS[task_index]
        checks.append(('navigation',navigation_ok(c,traj),'required local pages and relevant search/filter'))
        checks.append(('answer',answer_ok(task_index,str(traj.get('final_answer') or '')),'entity-bound facts, units and polarity'))
        ok,detail=state_ok(c,initial_db,after_db)
        checks.append(('snapshot_state',ok,detail))
    except (ValueError,KeyError,TypeError,sqlite3.Error,OSError) as exc:
        checks.append(('evidence_error',False,str(exc)))
    return dict(task_id=f'Cookpad--{task_index}',pass_=all(ok for _,ok,_ in checks),
                reason=next((name for name,ok,_ in checks if not ok),''),
                evidence=[f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}" for name,ok,detail in checks])

def main(task_index):
    p=argparse.ArgumentParser()
    p.add_argument('--run_dir',required=True);p.add_argument('--initial_db');p.add_argument('--after_db')
    p.add_argument('--container');p.add_argument('--no_llm',nargs='?',const='True')
    args=p.parse_args();run=Path(args.run_dir)
    verdict=evaluate(task_index,json.loads((run/'trajectory.json').read_text()),
                     args.initial_db or run/'initial.db',args.after_db or run/'after.db')
    verdict['pass']=verdict.pop('pass_')
    print(json.dumps(verdict,ensure_ascii=False,indent=2))
    sys.exit(0 if verdict['pass'] else 1)

if __name__=='__main__':
    raise SystemExit('Use a task-specific verify_N.py entrypoint.')
