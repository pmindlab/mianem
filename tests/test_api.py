from fastapi.testclient import TestClient
from app import __version__
from app.main import app


def test_health():
    client = TestClient(app)
    r = client.get('/api/health')
    assert r.status_code == 200
    data = r.json()
    assert data['ok'] is True
    assert data['app'] == 'Mianem'
    assert data['version'] == __version__
    assert data['workshop'] is True
    assert data['semantic_workshop'] is True
    assert data['construction_families'] is True
    assert data['niche_count'] >= 60


def test_languages():
    client = TestClient(app)
    r = client.get('/api/languages')
    assert r.status_code == 200
    keys = {x['key'] for x in r.json()['languages']}
    assert {'en','pl','es','fr','la','zh-pinyin'} <= keys


def test_workshop_lark():
    client = TestClient(app)
    r = client.post('/api/workshop', json={'root': 'lark', 'niche': 'birds', 'context': 'creative', 'limit': 8})
    assert r.status_code == 200
    data = r.json()
    assert data['root']['word'] == 'lark'
    assert 'skowronek' in data['root']['pl']
    assert data['before']
    assert data['after']
    assert data['best']
    assert data['before'][0]['word'] == 'dawn'
    assert data['after'][0]['word'] == 'wing'
    assert {'the', 'one'} <= {x['word'] for x in data['extensions']}
    assert data['families']
