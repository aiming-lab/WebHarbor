"""Bounded T9/T10 CLI regressions using explicit read-only snapshot inputs.

DRIVER_TEST_INPUTS and DRIVER_TEST_OUT must point outside the candidate tree.
No actor/run inputs are changed; generated trajectories are mechanical cases.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

SITE=Path(__file__).resolve().parents[1]


def write_png(path, width=320, height=200):
    """Structurally valid PNG without third-party dependencies (repair002, H3)."""
    import struct
    import zlib
    raw = b''.join(b'\x00' + bytes((10, 20, 30)) * width for _ in range(height))

    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)
    path.write_bytes(b'\x89PNG\r\n\x1a\n'
                     + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
                     + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


class DriverQualifierRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if 'DRIVER_TEST_INPUTS' not in os.environ or 'DRIVER_TEST_OUT' not in os.environ:
            raise unittest.SkipTest('requires explicit isolated driver test input/output paths')
        cls.inputs=Path(os.environ['DRIVER_TEST_INPUTS']).resolve(strict=True)
        cls.out=Path(os.environ['DRIVER_TEST_OUT']).resolve()
        if cls.out.is_relative_to(SITE):
            raise ValueError('test evidence must be outside site source')
        cls.out.mkdir(exist_ok=False)
        cls.tasks=[json.loads(line) for line in (SITE/'tasks.jsonl').read_text().splitlines()]

    def check_cli(self, number, answer, expected):
        folder=self.out/self._testMethodName;folder.mkdir()
        task=self.tasks[number]
        if number in (9,10):
            path=('/drivers?series=GeForce+RTX+'+('50' if number==9 else '40')+
                  '+Series&branch='+('Game+Ready' if number==9 else 'Studio')+'&os=Windows+11')
        else:
            path='/products/geforce-rtx-5090'
        url='http://127.0.0.1:48082'+path
        trajectory={'task_id':task['id'],'query':task['ques'],'steps':[{'step':0,'url':url,'url_before':url,'url_after':url}],
                    'final_url':url,'final_answer':answer,'native_task':False}
        (folder/'task.json').write_text(json.dumps(task))
        (folder/'trajectory.json').write_text(json.dumps(trajectory))
        shots=folder/'screenshots'; shots.mkdir()
        for i in range(2):
            write_png(shots/f'step_{i:03d}.png')
        cmd=[sys.executable,'-B',str(SITE/'verify'/f'verify_{number}.py'),'--run_dir',str(folder),
             '--initial_db',str(self.inputs/'initial.db'),'--after_db',str(self.inputs/'after.db')]
        r=subprocess.run(cmd,cwd=folder,env={'PATH':os.defpath,'PYTHONDONTWRITEBYTECODE':'1','PYTHONNOUSERSITE':'1'},capture_output=True,text=True,timeout=10)
        (folder/'stdout.txt').write_text(r.stdout);(folder/'stderr.txt').write_text(r.stderr)
        files=[folder/'task.json',folder/'trajectory.json',self.inputs/'initial.db',self.inputs/'after.db']
        receipt={'command':cmd,'expected_exit':expected,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr,
                 'input_hashes':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'mechanical_not_native':True}
        (folder/'receipt.json').write_text(json.dumps(receipt,indent=2))
        self.assertEqual(r.returncode,expected,r.stdout+r.stderr)
        value=json.loads(r.stdout)
        self.assertEqual(value['task_id'],task['id'])
        self.assertIs(value['pass'],expected==0)

    def test_other_information_task_not_relaxed(self):
        self.check_cli(0,'32 GB GDDR7. This is a frozen historical catalog, not a live release feed.',1)


QUALIFIER='The Drivers page identifies this as a frozen historical catalog, not a live release feed.'
for number in (9,10):
    v='566.36' if number==9 else '566.14'
    branch='Game Ready' if number==9 else 'Studio'
    wrong_branch='Studio' if number==9 else 'Game Ready'
    series='50' if number==9 else '40'
    good=f'The listed {branch} driver for GeForce RTX {series} Series on Windows 11 is version {v}.'
    cases={
        'historical_qualifier':(good+' '+QUALIFIER,0),
        'qualifier_before_facts':(QUALIFIER+' '+good,0),
        'same_sentence_qualifier':(good.rstrip('.')+', from a historical snapshot, not a real-time driver release feed.',0),
        'contraction_qualifier':(good+" This historical catalog isn't a live driver release feed.",0),
        'plain_version':(v,0),
        'version_denial':(f'The version is not {v}. '+QUALIFIER,1),
        'same_sentence_denial':(f'A frozen historical catalog, not a live release feed, and the version is not {v}.',1),
        'uncertain_version':(f'Maybe the version is {v}. '+QUALIFIER,1),
        'unknown_in_same_sentence':(f'This frozen catalog is not a live feed; the version {v} is unknown.',1),
        'wrong_branch':(f'{wrong_branch} {v}. '+QUALIFIER,1),
        'wrong_version':(good.replace(v,'999.99')+' '+QUALIFIER,1),
        'additional_wrong_version_same_sentence':(good+' Frozen historical catalog, not a live release feed, version 999.99.',1),
        'wrong_os':(good.replace('Windows 11','Linux')+' '+QUALIFIER,1),
        'version_embedded_in_denial':(f'Frozen historical catalog, not a live {v} release feed.',1),
    }
    for label,(text,expected) in cases.items():
        def test(self,n=number,answer=text,code=expected):
            self.check_cli(n,answer,code)
        setattr(DriverQualifierRegression,f'test_t{number}_{label}',test)
