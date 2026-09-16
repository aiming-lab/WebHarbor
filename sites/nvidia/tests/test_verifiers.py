#!/usr/bin/env python3
"""Mechanical verifier contract suite using an explicit full-schema seed copy.

python -B tests/test_verifiers.py --seed /absolute/seed.db --out /new/evidence/dir
This is not a browser/native test. Every case retains inputs and CLI output.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys

SITE = Path(__file__).resolve().parents[1]
INFO = set(range(12)) | {18}
STATE = set(range(20)) - INFO
ANSWERS = {
    0: '32 GB of GDDR7 memory', 1: '10,752 CUDA cores', 2: '450 W',
    3: 'GeForce RTX 5060: $299', 4: 'NVIDIA H200 Tensor Core GPU',
    5: 'Jetson Orin Nano Super Developer Kit: 8 GB, a developer kit; Jetson Orin NX 16GB: 16 GB, a production module.',
    6: 'The RTX 5090 has 5,376 more CUDA cores than the RTX 4090.',
    7: 'The RTX 5080 has higher memory bandwidth than the RTX 4080 SUPER.',
    8: 'RTX PRO 6000 Blackwell: 96 GB', 9: '566.36', 10: '566.14',
    11: 'Blackwell architecture; fifth-generation Tensor cores; fourth-generation RT cores. RTX 5080: NVIDIA Marketplace, United States (en-us).',
    18: 'Jun 16, 2026',
}
URLS = {
    0: ['/products/geforce-rtx-5090'], 1: ['/products/geforce-rtx-5080'],
    2: ['/products/geforce-rtx-4090'], 3: ['/products?category=geforce-gaming&series=RTX+50+Series'],
    4: ['/products/h200-tensor-core'],
    5: ['/products/jetson-orin-nano-super', '/products/jetson-orin-nx'],
    6: ['/compare?ids=geforce-rtx-5090%2Cgeforce-rtx-4090'],
    7: ['/compare?ids=geforce-rtx-5080%2Cgeforce-rtx-4080-super'],
    8: ['/products/rtx-pro-6000-blackwell', '/products/rtx-6000-ada'],
    9: ['/drivers?series=GeForce+RTX+50+Series&branch=Game+Ready&os=Windows+11'],
    10: ['/drivers?series=GeForce+RTX+40+Series&branch=Studio&os=Windows+11'],
    11: ['/geforce/graphics-cards/50-series/', '/where-to-buy/geforce-rtx-5080'],
    12: ['/account/wishlist'], 13: ['/account/wishlist'], 14: ['/account'],
    15: ['/products/jetson-orin-nano-super'], 16: ['/products/rtx-pro-6000-blackwell'],
    17: ['/account/wishlist'], 18: ['/news/blackwell-mlperf-training-6-0'], 19: ['/'],
}
NEAR = {
    0: ['132 GB GDDR7', '32 MB GDDR7', '32 GB GDDR6', 'RTX 5080: 32 GB GDDR7'],
    1: ['110752 CUDA cores', '10752 tensor cores', '10751 CUDA cores',
        'CUDA Cores: 11,752', 'Tensor Cores: 10,752'],
    2: ['1450 W', '450 kW', '449 W'],
    3: ['RTX 5060 Ti: $299', 'RTX 5060: $1299', 'RTX 5070: $299', 'RTX 5060',
        'RTX 5060 is the most expensive at $299'],
    4: ['GH200', 'H100', 'H200 with 144 GB'],
    5: ['Jetson Orin Nano Super: 16 GB developer kit; Jetson Orin NX: 8 GB production module',
        'Jetson Orin Nano Super: 8 GB production module; Jetson Orin NX: 16 GB developer kit',
        'Jetson Orin Nano Super Developer Kit: 8 GB'],
    6: ['RTX 4090 has 5376 more CUDA cores than RTX 5090',
        'RTX 5090 has 5376 more tensor cores than RTX 4090',
        'RTX 5090 has 5375 more CUDA cores than RTX 4090',
        'RTX 5090 has the same CUDA cores as RTX 4090, delta 5376'],
    7: ['RTX 5080 has lower memory bandwidth than RTX 4080 SUPER',
        'RTX 5080 and RTX 4080 SUPER have equal memory bandwidth',
        'RTX 4080 SUPER has higher bandwidth than RTX 5080',
        'RTX 5080 has higher bandwidth: 736 GB/s; RTX 4080 SUPER: 960 GB/s',
        'RTX 5080 has higher bandwidth: 960 MB/s; RTX 4080 SUPER: 736 MB/s',
        'RTX 5080 has higher bandwidth than RTX 4090'],
    8: ['RTX PRO 6000 Blackwell: 196 GB', 'RTX 6000 Ada: 96 GB', 'RTX PRO 6000 Blackwell: 96 MB'],
    9: ['566.360', '566.14', 'Studio 566.36', 'RTX 40 Series Game Ready 566.36'],
    10: ['566.140', '566.36', 'Game Ready 566.14', 'RTX 50 Series Studio 566.14'],
    11: ['Ada Lovelace, fifth-generation Tensor cores, fourth-generation RT cores. RTX 5080 NVIDIA Marketplace United States',
         'Blackwell, fourth-generation Tensor cores, fifth-generation RT cores. RTX 5080 NVIDIA Marketplace United States',
         'Blackwell, fifth-generation Tensor cores, fourth-generation RT cores. RTX 5080 NVIDIA Marketplace Canada',
         'Blackwell, fifth-generation Tensor cores, fourth-generation RT cores. RTX 5090 NVIDIA Marketplace United States',
         'Blackwell, fifth-generation Tensor cores, fourth-generation RT cores. RTX 5080 Amazon United States',
         'Blackwell, fifth-generation Tensor cores, fourth-generation RT cores. Tensor cores: 4th generation. RTX 5080 NVIDIA Marketplace United States'],
    18: ['June 16, 2025', 'June 15, 2026', 'June 16', 'Jun 16, 2026 or Jun 17, 2026'],
}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_png(path, width=320, height=200, payload=None):
    """Write a structurally valid PNG without any third-party dependency."""
    import struct
    import zlib
    path = Path(path)
    if payload is not None:
        path.write_bytes(payload)
        return path
    raw = b''.join(b'\x00' + bytes((10, 20, 30)) * width for _ in range(height))

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)
    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(raw))
           + chunk(b'IEND', b''))
    path.write_bytes(png)
    return path


TINY_PNG = bytes.fromhex(
    '89504e470d0a1a0a0000000d4948445200000001000000010806000000'
    '1f15c4890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082')


def write(path, obj):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


class Suite:
    def __init__(self, seed, out):
        self.seed, self.out = seed.resolve(strict=True), out.resolve()
        self.out.mkdir(parents=True, exist_ok=False)
        self.tasks = [json.loads(line) for line in (SITE/'tasks.jsonl').read_text().splitlines()]
        self.records = []
        with sqlite3.connect(self.seed.as_uri()+'?mode=ro', uri=True) as db:
            self.products = dict(db.execute('SELECT slug,id FROM products'))
            self.users = dict(db.execute('SELECT email,id FROM users'))
            assert db.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
            assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        write(self.out/'source.json', {'seed': str(self.seed), 'seed_sha256': digest(self.seed),
                                     'files': {str(p.relative_to(SITE)): digest(p) for p in
                                               [SITE/'tasks.jsonl', *sorted((SITE/'verify').glob('*.py')), Path(__file__)]},
                                     'evidence_kind': 'mechanical full-schema SQLite copies, not native'})

    def changes(self, number, wrong=False):
        uid = self.users['bob.c@test.com' if wrong else 'alice.j@test.com']
        target = {12: 'geforce-rtx-4060', 13: 'geforce-rtx-5070-ti', 17: 'geforce-rtx-5060-ti'}
        if number in target:
            return [('INSERT INTO wishlist_items(user_id,product_id) VALUES(?,?)', (uid, self.products[target[number]]))]
        if number == 14:
            return [("UPDATE users SET country='Germany' WHERE id=?", (uid,))]
        if number == 15:
            return [("INSERT INTO reviews(product_id,user_id,rating,title,body,created) VALUES(?,?,5,'Incredible','A useful developer kit.','2026-06-01')", (self.products['jetson-orin-nano-super'], uid))]
        if number == 16:
            return [('DELETE FROM wishlist_items WHERE user_id=? AND product_id=?', (uid, self.products['rtx-pro-6000-blackwell']))]
        if number == 19:
            return [("INSERT INTO newsletter(email,topic) VALUES(?,'GeForce')", ('wrong@example.com' if wrong else 'gamer42@example.com',))]
        return []

    def case(self, n, label, expected, *, answer=None, urls=None, before=(), changes=None, corrupt=None, final=None):
        folder = self.out/f'task-{n:03d}-{label}'
        folder.mkdir()
        shutil.copyfile(self.seed, folder/'initial.db')
        def sql(path, statements):
            with sqlite3.connect(path) as db:
                for command, parameters in statements:
                    db.execute(command, parameters)
        sql(folder/'initial.db', before)
        shutil.copyfile(folder/'initial.db', folder/'after.db')
        mutations = self.changes(n) if changes is None else changes
        sql(folder/'after.db', mutations)
        task = dict(self.tasks[n])
        paths = URLS[n] if urls is None else urls
        addresses = [p if p.startswith('http') else 'http://127.0.0.1:48082'+p for p in paths]
        # Native-ready emits url AND url_before/url_after and separate final_url.
        steps = [{'step': i, 'query': task['ques'], 'url_before': url, 'url': url, 'url_after': url}
                 for i, url in enumerate(addresses)]
        trajectory = {'task_id': task['id'], 'query': task['ques'], 'steps': steps,
                      'final_answer': ANSWERS.get(n, '') if answer is None else answer,
                      'status': 'DONE' if steps else 'NO_OP', 'terminated': bool(steps)}
        if addresses:
            trajectory['final_url'] = addresses[-1] if final is None else 'http://127.0.0.1:48082'+final
        if corrupt == 'identity': trajectory['task_id'] = 'NVIDIA--999'
        if corrupt == 'query': trajectory['query'] += ' changed'
        if corrupt == 'prod-shape':
            # Production recorder shape (agent_demo/agent.py): `task` instead of `query`,
            # no final_url. Must be accepted (repair002 contract).
            trajectory.pop('query')
            trajectory['task'] = task['ques']
            trajectory['start_url'] = addresses[0] if addresses else 'http://127.0.0.1:48082/'
            trajectory['termination_reason'] = 'agent_done'
            trajectory.pop('final_url', None)
        if corrupt == 'task': task['ques'] += ' changed'
        if corrupt == 'steps': trajectory['steps'] = [{'step': '0', 'url': addresses[0]}]
        if corrupt == 'url': trajectory['steps'] = [{'step': 0, 'url': 123}]
        write(folder/'task.json', task)
        write(folder/'trajectory.json', trajectory)
        if corrupt == 'json': (folder/'trajectory.json').write_text('{')
        if corrupt == 'altered-task':
            altered = dict(json.loads((folder/'task.json').read_text()))
            altered['ques'] = altered['ques'] + ' changed'
            (folder/'task.json').write_text(json.dumps(altered, ensure_ascii=False, indent=2) + '\n')
        if corrupt == 'schema': sql(folder/'after.db', [('DROP TABLE newsletter', ())])
        if corrupt == 'db': (folder/'after.db').write_bytes(b'not SQLite')
        if corrupt == 'missing-task': (folder/'task.json').unlink()
        if corrupt == 'missing-db': (folder/'after.db').unlink()
        # Screenshot evidence (repair002, H3): every case carries real PNGs unless the
        # case is specifically about screenshot defects.
        shots = folder / 'screenshots'
        if corrupt != 'no-screenshots':
            shots.mkdir(exist_ok=True)
            for i in range(len(steps) + 1):
                target = shots / f'step_{i:03d}.png'
                if corrupt == 'tiny-screenshots':
                    write_png(target, payload=TINY_PNG)
                elif corrupt == 'corrupt-screenshot':
                    write_png(target, payload=b'\x89PNG\r\n\x1a\n' + b'\x00' * 8)
                else:
                    write_png(target)
        if corrupt == 'missing-referenced-screenshot':
            traj = json.loads((folder/'trajectory.json').read_text())
            if traj['steps']:
                traj['steps'][0]['screenshot_before'] = 'step_999.png'
                write(folder/'trajectory-2.json', traj)
                (folder/'trajectory.json').write_text(json.dumps(traj, indent=2) + '\n')
        command = [sys.executable, '-B', str(SITE/'verify'/f'verify_{n}.py'), '--run_dir', str(folder),
                   '--initial_db', str(folder/'initial.db'), '--after_db', str(folder/'after.db')]
        inputs = {p.name: digest(p) for p in folder.iterdir() if p.is_file()}
        result = subprocess.run(command, cwd=folder, env={'PATH': os.defpath, 'PYTHONDONTWRITEBYTECODE': '1',
                               'PYTHONNOUSERSITE': '1'}, capture_output=True, text=True, timeout=15)
        (folder/'stdout.txt').write_text(result.stdout)
        (folder/'stderr.txt').write_text(result.stderr)
        try: value = json.loads(result.stdout)
        except ValueError: value = None
        sound = (isinstance(value, dict) and value.get('task_id') == self.tasks[n]['id'] and
                 type(value.get('pass')) is bool and result.returncode in (0, 1, 2) and
                 value['pass'] == (result.returncode == 0) and
                 (result.returncode != 2 or value.get('error') == 'INFRA_ERROR'))
        actual = result.returncode if sound else 'INVALID_OUTPUT'
        unchanged = all((folder/name).exists() and digest(folder/name) == h for name, h in inputs.items())
        record = {'task_id': self.tasks[n]['id'], 'case': label, 'command': command,
                  'expected_exit': expected, 'exit_code': result.returncode, 'actual': actual,
                  'input_hashes': inputs, 'input_unchanged': unchanged, 'before_sql': before, 'after_sql': mutations,
                  'stdout': result.stdout, 'stderr': result.stderr,
                  'ok': actual == expected and unchanged, 'evidence_kind': 'mechanical'}
        write(folder/'receipt.json', record)
        self.records.append(record)

    def run(self):
        for n in range(20):
            self.case(n, 'noop', 1, answer='', urls=[], changes=[])
            self.case(n, 'valid', 0)
            self.case(n, 'wrong-task-id', 2, corrupt='identity')
            self.case(n, 'task-mismatch', 2, corrupt='task')
            self.case(n, 'schema-error', 2, corrupt='schema')
            self.case(n, 'extra-order', 1, changes=self.changes(n)+[("INSERT INTO orders(user_id,status,total_usd) VALUES(?,'Processing',999)", (self.users['alice.j@test.com'],))])
            if n in INFO:
                self.case(n, 'no-evidence', 1, urls=[])
                for i, answer in enumerate(NEAR[n]): self.case(n, f'near-{i:02d}', 1, answer=answer)
            else:
                self.case(n, 'claim-no-delta', 1, answer='Done!', changes=[])
                self.case(n, 'wrong-account', 1, changes=self.changes(n, True))
                self.case(n, 'preexisting-noop', 1, before=self.changes(n), changes=[])
                self.case(n, 'wrong-target', 1, changes=self.wrong_target(n))
        for n in (12, 13, 17):
            self.case(n, 'duplicate-target', 1, changes=self.changes(n)*2)
            self.case(n, 'extra-wishlist', 1, changes=self.changes(n)+[('INSERT INTO wishlist_items(user_id,product_id) VALUES(?,?)', (self.users['alice.j@test.com'], self.products['geforce-rtx-5070']))])
            self.case(n, 'lost-old-item', 1, changes=self.changes(n)+[('DELETE FROM wishlist_items WHERE product_id=?', (self.products['geforce-rtx-4080-super'],))])
        self.case(14, 'changed-name', 1, changes=self.changes(14)+[("UPDATE users SET name='Other' WHERE email='alice.j@test.com'", ())])
        self.case(15, 'negated-title', 1, changes=self.changes(15)+[("UPDATE reviews SET title='Not Incredible' WHERE title='Incredible'", ())])
        self.case(15, 'wrong-stars', 1, changes=self.changes(15)+[("UPDATE reviews SET rating=4 WHERE title='Incredible'", ())])
        self.case(15, 'body-only-token', 1, changes=self.changes(15)+[("UPDATE reviews SET title='Bad',body='Incredible' WHERE title='Incredible'", ())])
        self.case(15, 'normalized-title', 0, changes=self.changes(15)+[("UPDATE reviews SET title='  INCREDIBLE  ' WHERE title='Incredible'", ())])
        self.case(16, 'delete-both', 1, changes=[("DELETE FROM wishlist_items WHERE user_id=?", (self.users['alice.j@test.com'],))])
        self.case(16, 'full-login-detail-route', 0, urls=['/', '/login', '/account', '/products/rtx-pro-6000-blackwell'])
        self.case(16, 'wishlist-route', 0, urls=['/account/wishlist'])
        self.case(16, 'preserve-third-item', 0, before=[('INSERT INTO wishlist_items(user_id,product_id) VALUES(?,?)', (self.users['alice.j@test.com'], self.products['geforce-rtx-5070']))])
        for n in (6, 7):
            self.case(n, 'empty-comparison', 1, urls=['/compare'])
            self.case(n, 'one-product', 1, urls=['/compare?ids=geforce-rtx-5080'])
        self.case(7, 'both-details', 0, urls=['/products/geforce-rtx-5080', '/products/geforce-rtx-4080-super'])
        for n, slugs in [(5, ('jetson-orin-nano-super', 'jetson-orin-nx')),
                         (6, ('geforce-rtx-5090', 'geforce-rtx-4090')),
                         (7, ('geforce-rtx-5080', 'geforce-rtx-4080-super'))]:
            self.case(n, 'native-get-comparison', 0, urls=['/compare?product='+slugs[0]+'&product='+slugs[1]])
        self.case(6, 'product-overrides-ids', 1,
                  urls=['/compare?product=geforce-rtx-5080&ids=geforce-rtx-5090,geforce-rtx-4090'])
        # Extended PR #107 fix round: the T5 rubric requires specifications for BOTH
        # Jetson products and fails one-product-only evidence, so the earlier
        # "one detail page is sufficient" pin (CQ-06) is replaced by "both products".
        self.case(5, 'one-jetson-page-insufficient', 1, urls=['/products/jetson-orin-nano-super'])
        self.case(5, 'other-jetson-page-only-insufficient', 1, urls=['/products/jetson-orin-nx'])
        self.case(5, 'both-jetson-details', 0,
                  urls=['/products/jetson-orin-nano-super', '/products/jetson-orin-nx'])
        # Extended round: T3 requires the model as well as the price.
        self.case(3, 'bare-price-only', 1, answer='$299')
        self.case(3, 'model-and-price', 0, answer='GeForce RTX 5060: $299')
        # Extended round: the rubric's own T6 sentence shape and a trailing delta.
        self.case(1, 'spec-row-echo', 0, answer='CUDA Cores: 10,752')
        self.case(6, 'rubric-wording', 0,
                  answer='The GeForce RTX 5090 has 5,376 more CUDA cores than the GeForce RTX 4090 (21,760 versus 16,384).')
        self.case(6, 'trailing-delta', 0,
                  answer='The GeForce RTX 5090 has 21,760 CUDA cores while the GeForce RTX 4090 has 16,384; that is 5,376 more.')
        self.case(6, 'swapped-absolute-counts', 1,
                  answer='The RTX 5090 has 16,384 CUDA cores and the RTX 4090 has 21,760, so the 5090 has 5,376 more.')
        for n in (9, 10):
            self.case(n, 'empty-drivers', 1, urls=['/drivers'])
            # A broad search is valid, but the requested series must be pinned: branch
            # and OS may stay unset, an absent series filter may not (extended round).
            self.case(n, 'series-only-broad', 0,
                      urls=['/drivers?series=' + ('GeForce+RTX+50+Series' if n == 9 else 'GeForce+RTX+40+Series')])
            self.case(n, 'no-series-filter', 1, urls=['/drivers?os=Windows+11'])
            self.case(n, 'branch-os-only-insufficient', 1,
                      urls=['/drivers?branch=' + ('Game+Ready' if n == 9 else 'Studio') + '&os=Windows+11'])
            self.case(n, 'linux-only', 1, urls=['/drivers?os=Linux'])
        self.case(18, 'unrelated-article', 1, urls=['/news/halos-os-robotaxi-safety'])
        self.case(18, 'news-list', 0, urls=['/news'])
        self.case(18, 'news-search', 0, urls=['/search?q=MLPerf'])
        # Extended round: a numeric-only search query carries no word evidence.
        self.case(18, 'news-search-numeric-only', 1, urls=['/search?q=6.0'])
        # Extended round: the newsletter row's topic is part of the requested state.
        self.case(19, 'wrong-topic', 1,
                  changes=[("INSERT INTO newsletter(email,topic) VALUES(?, 'NotTheGeForceTopic')",
                            ('gamer42@example.com',))])
        self.case(19, 'geforce-topic', 0)
        self.case(11, 'missing-technology', 1, urls=['/where-to-buy/geforce-rtx-5080'])
        self.case(11, 'missing-buying', 1, urls=['/geforce/graphics-cards/50-series/'])
        self.case(11, 'wrong-final-page', 1, final='/')
        self.case(11, 'reversed-browsing-order', 0, urls=['/where-to-buy/geforce-rtx-5080', '/geforce/graphics-cards/50-series/', '/where-to-buy/geforce-rtx-5080'])
        self.case(11, 'off-origin', 1, urls=URLS[11]+['https://marketplace.nvidia.com/en-us/consumer/graphics-cards/'])
        for label in ('query', 'steps', 'url', 'json', 'db', 'missing-db'):
            self.case(0, 'infra-'+label, 2, corrupt=label)
        # repair002 contract: task.json is an optional sidecar (the production recorder
        # does not write one), so its absence is accepted; an altered one is still INFRA,
        # and the production recorder's key set (`task`, no `query`, no final_url) works.
        self.case(0, 'missing-task-json-accepted', 0, corrupt='missing-task')
        self.case(0, 'altered-task-json', 2, corrupt='altered-task')
        self.case(0, 'production-recorder-shape', 0, corrupt='prod-shape')
        self.case(0, 'no-screenshots', 2, corrupt='no-screenshots')
        self.case(0, 'tiny-screenshots', 2, corrupt='tiny-screenshots')
        self.case(0, 'corrupt-screenshot', 2, corrupt='corrupt-screenshot')
        self.case(0, 'missing-referenced-screenshot', 2, corrupt='missing-referenced-screenshot')
        formats = {0: ['32GB GDDR7', '32 gigabytes of GDDR7.', '32 GB GDDR 7'],
                   1: ['10 752 CUDA cores', '10752', '10,752 CUDA cores.'],
                   2: ['450 watts.', '450', '0.45 kW'], 3: ['RTX 5060 costs USD 299.00.', 'RTX 5060 costs 299 US dollars'],
                   5: ['Jetson Orin Nano Super Developer Kit: 8 GB developer kit, not a production module; Jetson Orin NX 16GB: 16 GB production module, not a developer kit'],
                   6: ['RTX 5090 has 5 376 more CUDA cores than RTX 4090', 'RTX 5090 has 5,376 more cores'],
                   7: ['RTX 5080', 'RTX 5080 has higher bandwidth: 960 GB/s; RTX 4080 SUPER: 736 GB/s',
                       'RTX 5080 (960 GB/s) > RTX 4080 SUPER (736 GB/s)'],
                   9: ['Version 566.36.'], 10: ['Version 566.14.'],
                   11: ['Blackwell: Tensor cores: 5th generation; RT cores: 4th generation. RTX 5080 NVIDIA Marketplace, USA.',
                        ANSWERS[11]+' I did not place an order or visit the external store.',
                        'Blackwell; fifth-generation Tensor cores; fourth-generation ray-tracing cores; NVIDIA Marketplace, United States.'],
                   18: ['16/06/2026', '2026-06-16', '16 June 2026', 'June 16th, 2026', '06/16/2026']}
        for n, variants in formats.items():
            for i, answer in enumerate(variants): self.case(n, f'format-{i:02d}', 0, answer=answer)
        # URL substring tricks and a foreign origin cannot stand in for page evidence.
        self.case(0, 'path-in-query', 1, urls=['/search?q=/products/geforce-rtx-5090'])
        self.case(0, 'unrelated-detail', 1, urls=['/products/shield-tv'])
        self.case(0, 'foreign-only', 1, urls=['https://example.com/products/geforce-rtx-5090'])
        self.case(0, 'harmless-download', 0, changes=[('UPDATE drivers SET download_count=download_count+1 WHERE id=1', ())])
        counts = Counter(r['actual'] for r in self.records)
        summary = {'cases': len(self.records), 'passed': sum(r['ok'] for r in self.records),
                   'failed': [dict(task_id=r['task_id'], case=r['case'], actual=r['actual'], expected=r['expected_exit'], stdout=r['stdout'], stderr=r['stderr']) for r in self.records if not r['ok']],
                   'verifier_exit_counts': dict(counts), 'seed_sha256_after': digest(self.seed)}
        write(self.out/'results.json', self.records)
        write(self.out/'summary.json', summary)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if not summary['failed'] else 1

    def wrong_target(self, n):
        uid = self.users['alice.j@test.com']
        if n in (12, 13, 17):
            return [('INSERT INTO wishlist_items(user_id,product_id) VALUES(?,?)', (uid, self.products['geforce-rtx-5070']))]
        if n == 14: return [("UPDATE users SET country='France' WHERE id=?", (uid,))]
        if n == 15:
            return [("INSERT INTO reviews(product_id,user_id,rating,title,body) VALUES(?,?,5,'Incredible','Body')", (self.products['geforce-rtx-5080'], uid))]
        if n == 16:
            return [('DELETE FROM wishlist_items WHERE user_id=? AND product_id=?', (uid, self.products['geforce-rtx-4080-super']))]
        return self.changes(n, True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(Suite(args.seed, args.out).run())


# T5-only unit discovery: `python -m unittest discover -s .../tests -v`.
# Does not run the full SQLite Suite above or modify any native evidence.
import importlib.util
import unittest


class JetsonComparisonRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('t5_answers', SITE/'verify/answers.py')
        cls.answers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.answers)

    def test_shared_memory_boundary_unchanged(self):
        self.assertTrue(self.answers.memory('32 GB GDDR7', 32, 'GDDR7'))
        self.assertFalse(self.answers.memory('132 GB GDDR7', 32, 'GDDR7'))
        self.assertFalse(self.answers.memory('32 MB GDDR7', 32, 'GDDR7'))


_T5_TABLE = (
    '| Product | Memory capacity | Product type |\n|---|---|---|\n'
    '| Jetson Orin Nano Super Developer Kit | 8 GB LPDDR5 | Developer kit, '
    'comprising a Jetson Orin Nano module and reference carrier board |\n'
    '| Jetson Orin NX 16GB | 16 GB LPDDR5 | Production module for integration '
    'into devices such as drones, robots, and smart cameras |'
)
_T5_PROSE = ('Jetson Orin Nano Super: 8 GB LPDDR5 developer kit; '
             'Jetson Orin NX: 16 GB LPDDR5 production module.')
_T5_CASES = {
    'table': (_T5_TABLE, True),
    'table_true_summary': (_T5_TABLE + '\n\nThe Orin NX 16GB has twice the memory capacity of the Nano Super Developer Kit.', True),
    'repeated_incomplete_mentions': (_T5_PROSE + ' The Nano Super is a developer kit. The Orin NX is a production module.', True),
    'split_fact_clauses': ('Nano Super has 8 GB. Nano Super is a developer kit. Orin NX has 16 GB. Orin NX is a production module.', True),
    'component_and_carrier': ('Nano Super: 8GB developer kit, includes a module and carrier board; Orin NX 16GB: production module', True),
    'repeated_full_product_name': ('Nano Super has 8 GB. The Nano Super Developer Kit is a developer kit comprising a Jetson Orin Nano module and reference carrier board. Orin NX: 16GB production module.', True),
    'inverse_summary': (_T5_PROSE + ' The Nano Super has half the memory of the Orin NX.', True),
    'more_memory_summary': (_T5_PROSE + ' Orin NX has more memory than Nano Super.', True),
    'pronoun_fact': ('Nano Super has 8 GB. It is a developer kit. Orin NX has 16 GB. It is a production module.', True),
    'correct_negative_identity': ('Nano Super: 8 GB developer kit, not a production module; Orin NX 16GB: production module, not a developer kit', True),
    'swapped_memory': (_T5_PROSE.replace('8 GB', '32 GB').replace('16 GB', '8 GB').replace('32 GB', '16 GB'), False),
    'swapped_identity': ('Nano Super: 8GB production module; Orin NX: 16GB developer kit', False),
    'wrong_memory_type': (_T5_TABLE.replace('8 GB LPDDR5', '8 GB GDDR7'), False),
    'wrong_unit': (_T5_TABLE.replace('8 GB LPDDR5', '8 MB LPDDR5'), False),
    'contradictory_extra_capacity': (_T5_PROSE + ' Nano Super actually has 16 GB.', False),
    'contradictory_extra_identity': (_T5_TABLE + '\nOrin NX is a developer kit.', False),
    'reversed_summary': (_T5_TABLE + '\nNano Super has twice the memory of Orin NX.', False),
    'false_tie_summary': (_T5_PROSE + ' Orin NX has the same memory as Nano Super.', False),
    'missing_nx_identity': ('Nano Super: 8GB developer kit; Orin NX 16GB. Orin NX has twice the memory of Nano Super.', False),
    'summary_alone': ('Orin NX 16GB has twice the memory of Nano Super Developer Kit.', False),
}
for _label, (_answer, _expected) in _T5_CASES.items():
    def _test(self, answer=_answer, expected=_expected):
        self.assertIs(self.answers.jetson_compare(answer), expected)
    setattr(JetsonComparisonRegression, 'test_t5_' + _label, _test)
