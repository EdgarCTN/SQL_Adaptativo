import atexit
import os
import shutil
import tempfile
from pathlib import Path

_DIR = Path(tempfile.mkdtemp(prefix="desafios_sql_tests_"))
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{(_DIR / 'test.db').as_posix()}",
        "SECRET_KEY": "clave-solo-para-pruebas-" + "0" * 32,
        "DOMINIO_INSTITUCIONAL": "",
        "SEED_USUARIO_DEMO": "true",
        "DEMO_EMAIL": "estudiante@demo.edu",
        "DEMO_PASSWORD": "Demo12345!",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.db import Base, SessionLocal, cargar_modelos, engine  # noqa: E402
from app.main import app  # noqa: E402

cargar_modelos()
API = "/api/v1"


@atexit.register
def _limpiar():
    engine.dispose()
    shutil.rmtree(_DIR, ignore_errors=True)


@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:  # el lifespan recrea tablas y siembra
        yield c


@pytest.fixture
def db():
    with SessionLocal() as s:
        yield s


def cabecera(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def registrar(client, nombre="Ana Pérez", correo="ana@uni.edu", contrasena="Clave12345"):
    return client.post(
        f"{API}/auth/registro", json={"nombre": nombre, "correo": correo, "contrasena": contrasena}
    )


def login(client, correo="ana@uni.edu", contrasena="Clave12345"):
    return client.post(f"{API}/auth/login", json={"correo": correo, "contrasena": contrasena})


def token_de(client, correo="ana@uni.edu", contrasena="Clave12345") -> str:
    return login(client, correo, contrasena).json()["access_token"]
