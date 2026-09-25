"""Exercise permissions and persistent outcomes through the actual Flask routes."""
from pathlib import Path
import importlib.util
import hashlib
import re
import shutil
import sys
import pytest

SITE=Path(__file__).resolve().parents[1]

@pytest.fixture()
def mirror(tmp_path, monkeypatch):
    for name in ['app.py','seed_data.py','migrate_seed.py']:
        shutil.copy2(SITE/name,tmp_path/name)
    shutil.copytree(SITE/'templates',tmp_path/'templates')
    shutil.copytree(SITE/'instance_seed',tmp_path/'instance_seed')
    shutil.copytree(SITE/'instance_seed',tmp_path/'instance')
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, 'seed_data', raising=False)
    spec=importlib.util.spec_from_file_location('app',tmp_path/'app.py')
    module=importlib.util.module_from_spec(spec);monkeypatch.setitem(sys.modules,'app',module);spec.loader.exec_module(module)
    module.app.config['TESTING']=True
    yield module
    with module.app.app_context():module.db.session.remove();module.db.engine.dispose()


def token(response):
    return re.search(r'name="csrf_token" value="([^"]+)"',response.get_data(as_text=True))[1]


def login(client):
    page=client.get('/login')
    return client.post('/login',data={'csrf_token':token(page),'email':'alice.j@test.com','password':'TestPass123!'})


def share(client,permission):
    login(client);page=client.get('/file/125/share')
    page=client.post('/file/125/share',data={'csrf_token':token(page),'label':'Test recipients','permission':permission},follow_redirects=True)
    return re.search(r'href="(/shared/[^"]+)"',page.get_data(as_text=True))[1]


@pytest.mark.parametrize('permission',['view','download'])
def test_private_link_permissions_and_return_navigation(mirror,permission):
    owner=mirror.app.test_client();url=share(owner,permission);recipient=mirror.app.test_client()
    page=recipient.get(url);assert page.status_code==200
    assert recipient.get('/preview/125').status_code==404
    preview=recipient.get(url+'/preview');assert preview.status_code==200
    assert f'href="{url}"' in preview.get_data(as_text=True)
    with mirror.app.app_context():
        initial_downloads=mirror.DownloadLog.query.count();initial_count=mirror.db.session.get(mirror.FileItem,125).download_count
    response=recipient.post(url+'/download',data={'csrf_token':token(page)} if permission=='download' else {'csrf_token':token(recipient.get('/login'))})
    assert response.status_code==(200 if permission=='download' else 403)
    if permission=='download':assert f'href="{url}"' in response.get_data(as_text=True)
    with mirror.app.app_context():
        assert mirror.DownloadLog.query.count()==initial_downloads+(permission=='download')
        assert mirror.db.session.get(mirror.FileItem,125).download_count==initial_count+(permission=='download')
    with mirror.app.app_context():
        mirror.db.session.get(mirror.FileItem,125).deleted=True;mirror.db.session.commit()
    assert recipient.get(url).status_code==404
    assert recipient.get(url+'/preview').status_code==404
    assert recipient.post(url+'/download',data={'csrf_token':token(recipient.get('/login'))}).status_code==404
    assert recipient.get('/shared/nonexistent/preview').status_code==404


def test_rename_history_is_actual_transition(mirror):
    client=mirror.app.test_client();login(client);page=client.get('/my-files?folder=1');csrf=token(page)
    for name in ['2027 Retreat Budget.xlsx','2027 Retreat Budget.xlsx']:
        assert client.post('/file/123/rename',data={'csrf_token':csrf,'filename':name}).status_code==302
    with mirror.app.app_context():
        rows=mirror.FileRename.query.all();assert len(rows)==1
        assert (rows[0].user_id,rows[0].file_id,rows[0].old_name,rows[0].new_name)==(1,123,'Alice Quarterly retreat budget.xlsx','2027 Retreat Budget.xlsx')
        assert rows[0].created_at<=mirror.db.session.get(mirror.FileItem,123).modified_at


def test_populated_startup_does_not_write(mirror):
    digest=lambda:hashlib.sha256(mirror.RUNTIME_DB_PATH.read_bytes()).hexdigest()
    before=digest();mirror.initialize_database();assert digest()==before
