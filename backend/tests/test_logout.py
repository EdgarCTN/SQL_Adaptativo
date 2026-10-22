from datetime import timedelta

from sqlalchemy import select

from app.core.db import ahora_utc
from app.core.seguridad import crear_token
from app.modules.auth.models import TokenRevocado, Usuario
from conftest import API, cabecera, login, registrar, token_de


def _sesion_nueva(client):
    registrar(client)
    return token_de(client)


def test_token_usado_tras_el_logout_da_401(client):
    token = _sesion_nueva(client)
    h = cabecera(token)
    assert client.get(f"{API}/auth/yo", headers=h).status_code == 200
    r = client.post(f"{API}/auth/logout", headers=h)
    assert r.status_code == 200 and r.json()["ok"] is True
    for metodo, ruta in (("get", "/auth/yo"), ("get", "/perfil"), ("get", "/desafios")):
        r = client.request(metodo.upper(), f"{API}{ruta}", headers=h)
        assert r.status_code == 401, ruta
        assert r.json()["error"] is True and "Cerraste esta sesión" in r.json()["mensaje"]
    assert client.post(f"{API}/auth/logout", headers=h).status_code == 401  # ya revocado


def test_otro_token_valido_sigue_funcionando(client):
    token_a = _sesion_nueva(client)
    token_b = token_de(client)  # segunda sesión del mismo usuario (otro jti)
    assert token_a != token_b
    assert client.post(f"{API}/auth/logout", headers=cabecera(token_a)).status_code == 200
    assert client.get(f"{API}/auth/yo", headers=cabecera(token_a)).status_code == 401
    assert client.get(f"{API}/auth/yo", headers=cabecera(token_b)).status_code == 200
    assert login(client).status_code == 200  # volver a entrar funciona


def test_logout_guarda_el_jti_y_borra_los_vencidos(client, db):
    ahora = ahora_utc()
    db.add(TokenRevocado(jti="viejo-vencido", expira_en=ahora - timedelta(hours=1)))
    db.add(TokenRevocado(jti="vigente-ajeno", expira_en=ahora + timedelta(hours=1)))
    db.commit()
    token = _sesion_nueva(client)
    assert client.post(f"{API}/auth/logout", headers=cabecera(token)).status_code == 200
    db.expire_all()
    jtis = set(db.scalars(select(TokenRevocado.jti)))
    assert "viejo-vencido" not in jtis and "vigente-ajeno" in jtis
    assert len(jtis) == 2


def test_token_expirado_sigue_dando_401_sin_romper(client, db):
    registrar(client)
    uid = db.scalar(select(Usuario.id).where(Usuario.correo == "ana@uni.edu"))
    vencido, _ = crear_token(uid, "estudiante", minutos=-5)
    r = client.post(f"{API}/auth/logout", headers=cabecera(vencido))
    assert r.status_code == 401 and r.json()["error"] is True
