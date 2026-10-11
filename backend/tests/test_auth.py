import jwt
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.seguridad import ALGORITMO, crear_token
from app.modules.auth.models import Usuario
from conftest import API, cabecera, login, registrar, token_de


def test_flujo_registro_login_perfil_logout(client):
    r = registrar(client)
    assert r.status_code == 201
    u = r.json()
    assert u["rol"] == "estudiante" and u["linea_base_completada"] is False
    assert "hash_password" not in u and "contrasena" not in u

    r = login(client)
    assert r.status_code == 200
    token = r.json()["access_token"]
    assert r.json()["usuario"]["correo"] == "ana@uni.edu"

    assert client.get(f"{API}/auth/yo", headers=cabecera(token)).json()["nombre"] == "Ana Pérez"
    assert client.get(f"{API}/perfil", headers=cabecera(token)).status_code == 200

    r = client.put(f"{API}/perfil", json={"nombre": "Ana María"}, headers=cabecera(token))
    assert r.status_code == 200 and r.json()["nombre"] == "Ana María"

    r = client.put(
        f"{API}/perfil",
        json={"contrasena_actual": "Clave12345", "contrasena_nueva": "Nueva98765"},
        headers=cabecera(token),
    )
    assert r.status_code == 200
    assert login(client).status_code == 401
    assert login(client, contrasena="Nueva98765").status_code == 200

    r = client.post(f"{API}/auth/logout", headers=cabecera(token))
    assert r.status_code == 200 and r.json()["ok"] is True


def test_registro_siempre_crea_estudiante(client):
    r = client.post(
        f"{API}/auth/registro",
        json={"nombre": "Eva", "correo": "eva@uni.edu", "contrasena": "Clave12345", "rol": "administrador"},
    )
    assert r.status_code == 201
    assert r.json()["rol"] == "estudiante"


def test_registro_correo_duplicado(client):
    assert registrar(client).status_code == 201
    r = registrar(client, correo="ANA@uni.edu")
    assert r.status_code == 409 and r.json()["error"] is True


@pytest.mark.parametrize(
    "cuerpo",
    [
        {},
        {"nombre": "A", "correo": "ana@uni.edu", "contrasena": "Clave12345"},
        {"nombre": "Ana", "correo": "no-es-correo", "contrasena": "Clave12345"},
        {"nombre": "Ana", "correo": "ana@uni.edu", "contrasena": "corta1"},
        {"nombre": "Ana", "correo": "ana@uni.edu", "contrasena": "sinnumeros"},
    ],
)
def test_registro_datos_invalidos(client, cuerpo):
    r = client.post(f"{API}/auth/registro", json=cuerpo)
    assert r.status_code == 422
    j = r.json()
    assert j["error"] is True and j["detalles"]
    assert "Field required" not in r.text and "String should" not in r.text


def test_registro_json_invalido(client):
    r = client.post(
        f"{API}/auth/registro", content="{no es json", headers={"Content-Type": "application/json"}
    )
    assert r.status_code == 422 and r.json()["error"] is True


def test_dominio_institucional(client, monkeypatch):
    monkeypatch.setattr(settings, "dominio_institucional", "uni.edu")
    assert registrar(client, correo="ana@gmail.com").status_code == 422
    assert registrar(client, correo="ana@uni.edu").status_code == 201


def test_login_credenciales_invalidas_mismo_mensaje(client):
    registrar(client)
    mala = login(client, contrasena="Incorrecta1")
    desconocido = login(client, correo="nadie@uni.edu")
    assert mala.status_code == desconocido.status_code == 401
    assert mala.json()["mensaje"] == desconocido.json()["mensaje"]


def test_login_usuario_inactivo(client, db):
    registrar(client)
    token = token_de(client)
    u = db.scalar(select(Usuario).where(Usuario.correo == "ana@uni.edu"))
    u.activo = False
    db.commit()
    assert login(client).status_code == 401
    assert client.get(f"{API}/auth/yo", headers=cabecera(token)).status_code == 401


@pytest.mark.parametrize("ruta", ["/auth/yo", "/perfil"])
def test_token_ausente_o_invalido(client, ruta):
    assert client.get(f"{API}{ruta}").status_code == 401
    assert client.get(f"{API}{ruta}", headers=cabecera("abc.def.ghi")).status_code == 401
    ajeno = jwt.encode({"sub": "1", "exp": 9999999999}, "otra-clave-" + "x" * 40, algorithm=ALGORITMO)
    assert client.get(f"{API}{ruta}", headers=cabecera(ajeno)).status_code == 401
    vencido, _ = crear_token(1, "estudiante", minutos=-1)
    r = client.get(f"{API}{ruta}", headers=cabecera(vencido))
    assert r.status_code == 401 and r.json()["error"] is True


def test_logout_sin_token(client):
    assert client.post(f"{API}/auth/logout").status_code == 401


@pytest.mark.parametrize(
    "cuerpo",
    [
        {},
        {"nombre": "A"},
        {"contrasena_nueva": "Nueva98765"},
        {"contrasena_actual": "Incorrecta1", "contrasena_nueva": "Nueva98765"},
        {"contrasena_actual": "Clave12345", "contrasena_nueva": "corta"},
    ],
)
def test_perfil_datos_invalidos_no_guarda(client, cuerpo):
    registrar(client)
    token = token_de(client)
    r = client.put(f"{API}/perfil", json=cuerpo, headers=cabecera(token))
    assert r.status_code == 422 and r.json()["error"] is True
    assert login(client).status_code == 200  # la contraseña sigue igual
    assert client.get(f"{API}/perfil", headers=cabecera(token)).json()["nombre"] == "Ana Pérez"
