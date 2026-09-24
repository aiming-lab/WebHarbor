import re
import pytest

ORDER={'quantity':'2','format':'Large Print','line1':'12 Elm Court','city':'Denver','state':'CO','zip':'80204'}

def token(client,path='/publication-ordering/10050'):
    return re.search(r'name="csrf_token" value="([^"]+)"',client.get(path).text)[1]

def test_csrf_and_private_persistent_anonymous_order(app,client):
    from app import PubOrder
    app.config['CSRF_ENABLED']=True
    assert client.post('/publication-ordering/10050',data=ORDER).status_code==400
    data={**ORDER,'csrf_token':token(client)}
    response=client.post('/publication-ordering/10050',data=data)
    assert response.status_code==302 and '/publication-orders/' in response.location
    for _ in range(2):
        body=client.get(response.location).text
        assert '12 Elm Court' in body and 'Large Print' in body and '2 copies' in body
    assert app.test_client().get(response.location).status_code==404
    with app.app_context():
        orders=PubOrder.query.all();assert len(orders)==1
        assert orders[0].user_id is None and orders[0].quantity==2
    assert client.get('/account/logout').status_code==405

@pytest.mark.parametrize('field,value',[('quantity','0'),('quantity','6'),('quantity','spam'),('format','PDF'),('line1',''),('city',''),('state','ZZ'),('zip','8020'),('zip','80204xxx')])
def test_bad_order_rejected_without_state_change(app,client,field,value):
    from app import PubOrder
    assert client.post('/publication-ordering/10050',data={**ORDER,field:value}).status_code==400
    with app.app_context():assert PubOrder.query.count()==0


def test_provider_browse_sort_pagination_and_context(client):
    body=client.get('/care-compare/providers/physicians').text
    assert 'loc=Boston,+MA' in body or 'loc=Boston,%20MA' in body
    from bs4 import BeautifulSoup
    root='/care-compare/search?type=Physician&loc=Boston,%20MA'
    soup=BeautifulSoup(client.get(root+'&sort=name').text,'html.parser')
    names=[x.get_text(strip=True) for x in soup.select('.result-card h3')]
    assert names==sorted(names,key=str.casefold)
    nxt=soup.find('a',string='Next page');assert nxt
    assert 'Showing 61 -' in client.get(nxt['href']).text
    href=soup.select_one('.result-card h3 a')['href']
    detail=BeautifulSoup(client.get(href).text,'html.parser')
    back=detail.find('a',string='← Back to results')['href']
    assert 'sort=name' in back and 'Boston' in back
    assert 'No providers match' in client.get(root+'&q=zzzznomatch').text


def test_plan_return_context_and_county_validation(client):
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(client.get('/plan-compare/search?zip=80204').text,'html.parser')
    href=soup.select_one('.plan-card h3 a')['href']
    detail=BeautifulSoup(client.get(href).text,'html.parser')
    assert 'zip=80204' in detail.find('a',string='← Back to plan results')['href']
    assert client.get('/plan-compare/search?zip=80204&county=Sangamon').status_code==400
    assert client.get('/plan-compare/search?zip=80204extra').status_code==400
    assert 'not current plan offers' in str(soup)


def test_no_external_form_redirect(client):
    assert client.post('/signup/email',data={'email':'bad','next':'https://example.com/'}).location=='/'


def test_repeat_payment_preserves_existing_bill(app,client):
    from app import PremiumBill
    client.post('/account/login',data={'email':'bob.c@test.com','password':'TestPass123!'})
    with app.app_context():
        prior=PremiumBill.query.filter_by(user_id=2,status='Paid').first()
        before=(prior.paid_date,prior.method);bid=prior.id
    client.post(f'/my/premiums/pay/{bid}',data={'method':'Bank account ending 4821'})
    with app.app_context():
        row=PremiumBill.query.filter_by(id=bid).first();assert (row.paid_date,row.method)==before
