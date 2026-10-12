"""Recorre todas las rutas del OpenAPI: sin token, con token inválido, como estudiante y como docente.

Ninguna debe responder 5xx; las protegidas dan 401 (sin sesión) o 403 (rol indebido) con JSON controlado.
"""
import re

import pytest
from fastapi.testclient import TestClient

from app.core.seguridad import hashear_password
from app.main import app
from app.modules.auth.models import Rol, Usuario
from conftest import API, cabecera, registrar, token_de

PUBLICAS = {f"{API}/health", f"{API}/auth/registro", f"{API}/auth/login"}
SOLO_ESTUDIANTE = ("/desafios", "/ayudas", "/linea-base", "/progreso")
METODOS = ("get", "post", "put", "delete", "patch")


def _rutas():
    esquema = app.openapi()
    for ruta, ops in esquema["paths"].items():
        for metodo in ops:
            if metodo in METODOS:
                yield metodo, ruta


def _con_id(ruta: str, valor: str) -> str:
    return re.sub(r"\{[^}]+\}", valor, ruta)


def _llamar(c: TestClient, metodo: str, ruta: str, headers=None):
    # Cuerpo vacío válido para cualquier POST/PUT: así también se prueban las validaciones 422.
    kwargs = {"json": {}} if metodo in ("post", "put", "patch") else {}
    return c.request(metodo.upper(), ruta, headers=headers, **kwargs)


@pytest.fixture
def sin_excepciones(client):
    """Cliente que devuelve el 500 en lugar de relanzar la excepción (se ejecuta tras sembrar la BD)."""
    return TestClient(app, raise_server_exceptions=False)


def _verificar_json_controlado(r, contexto):
    assert r.status_code < 500, f"{contexto} respondió {r.status_code}: {r.text[:200]}"
    if r.status_code >= 400:
        j = r.json()
        assert j.get("error") is True and j.get("mensaje"), f"{contexto}: error sin formato controlado"
        assert "Traceback" not in r.text


def test_hay_rutas_que_recorrer():
    rutas = {(m, r.removeprefix(API)) for m, r in _rutas()}
    esperadas = {
        ("get", "/health"), ("post", "/auth/login"), ("get", "/perfil"), ("get", "/linea-base/estado"),
        ("get", "/desafios"), ("post", "/desafios/{desafio_id}/intentos"), ("post", "/desafios/{desafio_id}/ayuda"),
        ("post", "/ayudas/{solicitud_id}/valoracion"), ("get", "/progreso/resumen"),
    }
    assert esperadas <= rutas  # si se añade una ruta nueva, el recorrido la incluye sola


def test_sin_token(sin_excepciones):
    for metodo, ruta in _rutas():
        r = _llamar(sin_excepciones, metodo, _con_id(ruta, "1"))
        _verificar_json_controlado(r, f"{metodo.upper()} {ruta} sin token")
        if ruta not in PUBLICAS:
            assert r.status_code == 401, f"{metodo.upper()} {ruta} sin token dio {r.status_code}"


def test_token_invalido(sin_excepciones):
    h = cabecera("esto.no.es.un.jwt")
    for metodo, ruta in _rutas():
        if ruta in PUBLICAS:
            continue
        r = _llamar(sin_excepciones, metodo, _con_id(ruta, "1"), h)
        _verificar_json_controlado(r, f"{metodo.upper()} {ruta} token inválido")
        assert r.status_code == 401


@pytest.mark.parametrize("valor_id", ["1", "99999", "abc"])
def test_como_estudiante(client, sin_excepciones, valor_id):
    registrar(client)
    h = cabecera(token_de(client))
    for metodo, ruta in _rutas():
        if ruta == f"{API}/auth/logout":
            continue  # no revoca nada, pero se prueba aparte para no depender del orden
        r = _llamar(sin_excepciones, metodo, _con_id(ruta, valor_id), h)
        _verificar_json_controlado(r, f"{metodo.upper()} {ruta} (id={valor_id}) como estudiante")
        assert r.status_code != 401, f"{metodo.upper()} {ruta} rechazó un token válido"
    assert sin_excepciones.post(f"{API}/auth/logout", headers=h).status_code == 200


def test_como_docente(client, db, sin_excepciones):
    db.add(
        Usuario(nombre="Profe", correo="profe@uni.edu", rol=Rol.docente.value, hash_password=hashear_password("Clave12345"))
    )
    db.commit()
    h = cabecera(token_de(client, "profe@uni.edu", "Clave12345"))
    for metodo, ruta in _rutas():
        r = _llamar(sin_excepciones, metodo, _con_id(ruta, "1"), h)
        _verificar_json_controlado(r, f"{metodo.upper()} {ruta} como docente")
        if ruta.removeprefix(API).startswith(SOLO_ESTUDIANTE):
            assert r.status_code == 403, f"{metodo.upper()} {ruta} dio {r.status_code} a un docente"


def test_ruta_inexistente_y_metodo_no_permitido(sin_excepciones):
    r = sin_excepciones.get(f"{API}/no-existe")
    assert r.status_code == 404 and r.json()["error"] is True
    r = sin_excepciones.delete(f"{API}/health")
    assert r.status_code == 405 and r.json()["error"] is True
