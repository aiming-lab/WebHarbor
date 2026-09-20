"""Build a deterministic local HF candidate; never publishes anything."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import tarfile
from PIL import Image

SITE=Path(__file__).resolve().parents[1]

def package(output):
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite {output}')
    sources=json.loads((SITE/'source_catalog.json').read_text())
    brands=json.loads((SITE/'brand_assets.json').read_text())
    expected={r['image_path']:r['image_sha256'] for r in sources}
    expected.update({r['path']:r['sha256'] for r in brands})
    for name,digest in expected.items():
        path=SITE/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Asset hash mismatch: '+name)
        with Image.open(path) as image:image.verify()
    files=['instance_seed/cookpad.db',*sorted(expected)]
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('xb') as raw, gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as gz, tarfile.open(fileobj=gz,mode='w') as archive:
        for name in files:
            path=SITE/name
            info=archive.gettarinfo(str(path),'cookpad/'+name)
            info.uid=info.gid=0;info.uname=info.gname='';info.mtime=0;info.mode=0o644
            with path.open('rb') as source:archive.addfile(info,source)
    manifest=dict(archive=output.name,sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                  published=False,files=[dict(path='cookpad/'+name,sha256=hashlib.sha256((SITE/name).read_bytes()).hexdigest()) for name in files])
    output.with_suffix(output.suffix+'.manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps(dict(archive=str(output),sha256=manifest['sha256'],files=len(files),published=False)))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    package(parser.parse_args().output)
