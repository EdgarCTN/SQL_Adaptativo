import atexit
import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

_DIR = Path(tempfile.mkdtemp(prefix="desafios_sql_tests_"))

# Por defecto las pruebas usan SQLite temporal. Con TEST_DATABASE_URL (PostgreSQL) corren contra esa base:
# las fixtures hacen drop_all/create_all, así que SOLO se acepta una base local (nunca Neon/producción).
_URL_PRUEBAS = os.environ.get("TEST_DATABASE_URL", "").strip()
if _URL_PRUEBAS:
    _host = urlparse(_URL_PRUEBAS.replace("postgresql+psycopg://", "postgresql://", 1)).hostname or ""
    if _host not in ("localhost", "127.0.0.1", "::1", "db", "postgres"):
        raise RuntimeError(f"TEST_DATABASE_URL apunta a un host no local ({_host}); las pruebas borran las tablas. Abortado.")
os.environ.update(
    {
        "ENTORNO": "desarrollo",  # nunca heredar ENTORNO=produccion del .env/entorno del desarrollador
        "DATABASE_URL": _URL_PRUEBAS or f"sqlite:///{(_DIR / 'test.db').as_posix()}",
        "SECRET_KEY": "clave-solo-para-pruebas-" + "0" * 32,
        "DOMINIO_INSTITUCIONAL": "",
        "SEED_USUARIO_DEMO": "true",
        "DEMO_EMAIL": "estudiante@demo.edu",
        "DEMO_PASSWORD": "Demo12345!",
        "DOCENTE_EMAIL": "",
        "DOCENTE_PASSWORD": "",
        "ADMIN_EMAIL": "",
        "ADMIN_PASSWORD": "",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
        # Las pruebas nunca deben heredar credenciales reales del .env del desarrollador.
        "LLM_PROVIDER": "mock",
        "GROQ_API_KEY": "",
        "ANTHROPIC_API_KEY": "",
        "OPENAI_API_KEY": "",
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


def pytest_collection_modifyitems(config, items):
    """Con TEST_DATABASE_URL (PostgreSQL) se omiten las pruebas marcadas solo_sqlite, indicándolo en el reporte."""
    if not _URL_PRUEBAS:
        return
    omitir = pytest.mark.skip(reason="solo_sqlite: depende de que DATABASE_URL sea un archivo SQLite")
    for item in items:
        if "solo_sqlite" in item.keywords:
            item.add_marker(omitir)
