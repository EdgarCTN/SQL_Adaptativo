from conftest import API


def test_health(client):
    r = client.get(f"{API}/health")
    assert r.status_code == 200
    assert r.json()["estado"] == "ok"
    assert r.json()["base_datos"] == "ok"


def test_ruta_inexistente_responde_json_amable(client):
    r = client.get(f"{API}/no-existe")
    assert r.status_code == 404
    cuerpo = r.json()
    assert cuerpo["error"] is True
    assert "Traceback" not in r.text and "Not Found" not in r.text


def test_metodo_no_permitido(client):
    r = client.delete(f"{API}/health")
    assert r.status_code == 405
    assert r.json()["error"] is True
