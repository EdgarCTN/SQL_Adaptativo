"""Respaldo y restauración de PostgreSQL (pg_dump/pg_restore).

Parte 1: pruebas con herramientas simuladas (no necesitan PostgreSQL; corren en SQLite y en CI).
Parte 2: ida y vuelta REAL; solo si TEST_DATABASE_URL es PostgreSQL y pg_dump/pg_restore están instalados.
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))

import respaldo  # noqa: E402
import restaurar  # noqa: E402
from respaldo import ErrorRespaldo  # noqa: E402

LISTA_OK = """;
; Archive created at 2026-11-22
3456; 0 16400 TABLE public usuarios -
3457; 0 16410 TABLE DATA public usuarios -
3458; 0 16420 TABLE DATA public desafios -
3459; 0 16430 TABLE DATA public alembic_version -
"""
LISTA_SIN_DESAFIOS = "3457; 0 16410 TABLE DATA public usuarios -\n"


def _url(host="ep-abc-123.us-east-2.aws.neon.tech", **extra):
    base = dict(
        drivername="postgresql+psycopg", host=host, port=None, username="neondb_owner", password="s3creta/+!",
        database="neondb", query={"sslmode": "require"},
    )
    base.update(extra)
    return SimpleNamespace(**base)


class FakePG:
    """Sustituye respaldo._ejecutar y _exigir_herramienta: registra los comandos y escribe un dump falso."""

    def __init__(self, monkeypatch, lista=LISTA_OK, falla_restore=False, falla_dump=False,
                 stderr_restore="pg_restore: error: relation already exists"):
        self.stderr_restore = stderr_restore
        self.llamadas: list[tuple[list[str], dict]] = []
        self.lista, self.falla_restore, self.falla_dump = lista, falla_restore, falla_dump
        monkeypatch.setattr(respaldo, "_exigir_herramienta", lambda nombre: f"/usr/bin/{nombre}")
        monkeypatch.setattr(respaldo, "_ejecutar", self)
        monkeypatch.setattr(restaurar, "_exigir_herramienta", lambda nombre: f"/usr/bin/{nombre}")

    def __call__(self, cmd, env):
        self.llamadas.append((cmd, env))
        herramienta = Path(cmd[0]).name
        if herramienta == "pg_dump":
            if self.falla_dump:
                return subprocess.CompletedProcess(cmd, 1, "", "pg_dump: error: connection failed")
            Path(cmd[cmd.index("--file") + 1]).write_bytes(b"PGDMP" + b"\x00" * 64)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if "--list" in cmd:
            return subprocess.CompletedProcess(cmd, 0, self.lista, "")
        if self.falla_restore:
            return subprocess.CompletedProcess(cmd, 1, "", self.stderr_restore)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def comandos(self, herramienta):
        return [c for c, _ in self.llamadas if Path(c[0]).name == herramienta]


def _dump_falso(ruta: Path) -> Path:
    ruta.write_bytes(b"PGDMP" + b"\x00" * 64)
    return ruta


# ---------------------------------------------------------------- conexión
def test_conexion_cambia_el_pooler_de_neon_por_el_host_directo():
    c = respaldo.conexion_pg(_url(host="ep-abc-123-pooler.us-east-2.aws.neon.tech"))
    assert c.host == "ep-abc-123.us-east-2.aws.neon.tech" and c.era_pooler
    c2 = respaldo.conexion_pg(_url())
    assert c2.host == "ep-abc-123.us-east-2.aws.neon.tech" and not c2.era_pooler


def test_la_clave_viaja_en_el_entorno_y_no_en_los_argumentos():
    c = respaldo.conexion_pg(_url())
    args = respaldo.args_conexion_pg(c)
    assert args == ["-h", "ep-abc-123.us-east-2.aws.neon.tech", "-U", "neondb_owner", "-d", "neondb"]
    assert all("s3creta" not in a for a in args)
    env = respaldo.entorno_pg(c)
    assert env["PGPASSWORD"] == "s3creta/+!" and env["PGSSLMODE"] == "require"
    assert "s3creta" not in repr(c)  # tampoco aparece al imprimir el objeto


def test_conexion_exige_nombre_de_base():
    with pytest.raises(ErrorRespaldo):
        respaldo.conexion_pg(_url(database=None))


# ---------------------------------------------------------------- respaldo
def test_respaldar_postgres_crea_dump_verificado(tmp_path, monkeypatch):
    fake = FakePG(monkeypatch)
    destino = respaldo.respaldar_postgres(respaldo.conexion_pg(_url()), tmp_path / "r")
    assert destino.suffix == ".dump" and destino.name.startswith("desafios_sql_") and respaldo.es_dump_pg(destino)
    assert [p.name for p in (tmp_path / "r").iterdir()] == [destino.name]  # sin .parcial
    cmd = fake.comandos("pg_dump")[0]
    assert "--format=custom" in cmd and "--no-owner" in cmd


def test_respaldar_rechaza_un_dump_sin_las_tablas_de_la_plataforma(tmp_path, monkeypatch):
    FakePG(monkeypatch, lista=LISTA_SIN_DESAFIOS)
    with pytest.raises(ErrorRespaldo, match="desafios"):
        respaldo.respaldar_postgres(respaldo.conexion_pg(_url()), tmp_path / "r")
    assert list((tmp_path / "r").glob("*")) == []


def test_respaldar_informa_el_fallo_de_pg_dump_en_espanol(tmp_path, monkeypatch):
    FakePG(monkeypatch, falla_dump=True)
    with pytest.raises(ErrorRespaldo, match="pg_dump falló"):
        respaldo.respaldar_postgres(respaldo.conexion_pg(_url()), tmp_path / "r")
    assert list((tmp_path / "r").glob("*")) == []


def test_sin_clientes_de_postgres_el_error_es_claro(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(ErrorRespaldo, match="clientes de PostgreSQL"):
        respaldo._exigir_herramienta("pg_dump")


# ---------------------------------------------------------------- restauración
def test_restaurar_postgres_hace_copia_de_seguridad_antes_y_es_todo_o_nada(tmp_path, monkeypatch):
    fake = FakePG(monkeypatch)
    copia = _dump_falso(tmp_path / "copia.dump")
    seguridad = restaurar.restaurar_postgres(copia, respaldo.conexion_pg(_url()), tmp_path / "seg")
    assert seguridad.name.startswith("antes_de_restaurar_") and seguridad.is_file()
    orden = [Path(c[0]).name + (" --list" if "--list" in c else "") for c, _ in fake.llamadas]
    assert orden.index("pg_dump") < orden.index("pg_restore")  # primero la copia de seguridad, luego el restore
    cmd = [c for c in fake.comandos("pg_restore") if "--list" not in c][0]
    for opcion in ("--clean", "--if-exists", "--single-transaction", "--exit-on-error", "--no-owner"):
        assert opcion in cmd
    assert cmd[-1] == str(copia)


def test_restaurar_postgres_si_falla_deja_la_copia_de_seguridad_y_avisa(tmp_path, monkeypatch):
    FakePG(monkeypatch, falla_restore=True)
    copia = _dump_falso(tmp_path / "copia.dump")
    with pytest.raises(ErrorRespaldo, match="quedó como estaba") as e:
        restaurar.restaurar_postgres(copia, respaldo.conexion_pg(_url()), tmp_path / "seg")
    assert "antes_de_restaurar_" in str(e.value) and len(list((tmp_path / "seg").glob("*.dump"))) == 1


def test_restaurar_explica_el_desajuste_de_versiones_cliente_servidor(tmp_path, monkeypatch):
    err = 'pg_restore: error: could not execute query: ERROR:  unrecognized configuration parameter "transaction_timeout"'
    FakePG(monkeypatch, falla_restore=True, stderr_restore=err)
    copia = _dump_falso(tmp_path / "copia.dump")
    with pytest.raises(ErrorRespaldo, match="MISMA versión mayor"):
        restaurar.restaurar_postgres(copia, respaldo.conexion_pg(_url()), tmp_path / "seg")


def test_restaurar_postgres_no_toca_nada_si_la_copia_no_es_valida(tmp_path, monkeypatch):
    fake = FakePG(monkeypatch)
    ajena = tmp_path / "x.dump"
    ajena.write_bytes(b"no es un dump")
    with pytest.raises(ErrorRespaldo, match="pg_dump --format=custom"):
        restaurar.restaurar_postgres(ajena, respaldo.conexion_pg(_url()), tmp_path / "seg")
    assert fake.llamadas == []  # ni siquiera se hizo la copia de seguridad


def test_restaurar_sin_copia_de_seguridad_no_continua(tmp_path, monkeypatch):
    fake = FakePG(monkeypatch, falla_dump=True)
    copia = _dump_falso(tmp_path / "copia.dump")
    with pytest.raises(ErrorRespaldo, match="pg_dump falló"):
        restaurar.restaurar_postgres(copia, respaldo.conexion_pg(_url()), tmp_path / "seg")
    assert all("--list" in c for c in fake.comandos("pg_restore"))  # solo la verificación; nunca el restore


# ---------------------------------------------------------------- ida y vuelta REAL (solo PostgreSQL)
_URL_PG = os.environ.get("TEST_DATABASE_URL", "")
_hay_pg = _URL_PG.startswith(("postgresql", "postgres")) and shutil.which("pg_dump") and shutil.which("pg_restore")


@pytest.mark.skipif(not _hay_pg, reason="requiere TEST_DATABASE_URL de PostgreSQL y pg_dump/pg_restore instalados")
def test_ida_y_vuelta_real_con_postgres(client, tmp_path):
    from conftest import registrar
    from sqlalchemy import text

    from app.core.db import SessionLocal, engine

    # pg_restore con clientes MÁS NUEVOS que el servidor falla (p. ej. cliente 17 -> servidor 16: transaction_timeout).
    cliente = re.search(r"\)\s*(\d+)", subprocess.run(["pg_restore", "--version"], capture_output=True, text=True).stdout)
    with engine.connect() as cn:
        servidor = int(cn.execute(text("SHOW server_version_num")).scalar()) // 10000
    if cliente and int(cliente.group(1)) > servidor:
        pytest.skip(f"clientes PostgreSQL {cliente.group(1)} más nuevos que el servidor {servidor}: usa clientes {servidor} "
                    f"o levanta el servidor con POSTGRES_VERSION={cliente.group(1)} (ver docker-compose.yml)")

    assert registrar(client, "Ñandú Quispe", "nq@uni.edu").status_code in (200, 201)
    c = respaldo.conexion_pg(respaldo.url_configurada())
    copia = respaldo.respaldar_postgres(c, tmp_path / "r")
    with SessionLocal() as s:
        s.execute(text("UPDATE usuarios SET nombre = 'ALTERADO' WHERE correo = 'nq@uni.edu'"))
        s.commit()
    engine.dispose()
    restaurar.restaurar_postgres(copia, c, tmp_path / "seg")
    engine.dispose()
    with SessionLocal() as s:
        nombre = s.execute(text("SELECT nombre FROM usuarios WHERE correo = 'nq@uni.edu'")).scalar_one()
    assert nombre == "Ñandú Quispe"  # la restauración deshizo el cambio
