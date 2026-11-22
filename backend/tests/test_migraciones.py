"""Migraciones: la cadena de Alembic debe producir el mismo esquema que los modelos (create_all).

Usan su propia BD SQLite temporal; no tocan la BD de las demás pruebas.
Si fallan por 'no hay migraciones', falta generar la migración inicial (docs/MIGRACIONES.md).
"""
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

from app.core.db import Base, cargar_modelos, verificar_esquema

BACKEND = Path(__file__).resolve().parents[1]
cargar_modelos()


def _cfg() -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.attributes["configure_logger"] = False
    return cfg


@pytest.fixture
def motor(tmp_path):
    eng = create_engine(f"sqlite:///{(tmp_path / 'm.db').as_posix()}")
    yield eng
    eng.dispose()


def _migrar(eng, destino="head"):
    cfg = _cfg()
    with eng.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, destino)


def _estructura(eng) -> dict[str, set[str]]:
    insp = inspect(eng)
    return {t: {c["name"] for c in insp.get_columns(t)} for t in insp.get_table_names() if t != "alembic_version"}


def test_hay_una_sola_cabeza_y_al_menos_una_migracion():
    cabezas = ScriptDirectory.from_config(_cfg()).get_heads()
    assert len(cabezas) == 1, f"Se esperaba 1 cabeza de migraciones y hay {len(cabezas)}: {cabezas}"


def test_upgrade_head_coincide_con_los_modelos(motor):
    _migrar(motor)
    with motor.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diff == [], f"Los modelos y las migraciones difieren (genera una migración nueva): {diff}"


def test_mismas_tablas_y_columnas_que_create_all(motor, tmp_path):
    _migrar(motor)
    ref = create_engine(f"sqlite:///{(tmp_path / 'ref.db').as_posix()}")
    Base.metadata.create_all(bind=ref)
    try:
        assert _estructura(motor) == _estructura(ref)
    finally:
        ref.dispose()


def test_downgrade_base_deja_la_bd_vacia(motor):
    _migrar(motor)
    cfg = _cfg()
    with motor.begin() as conn:
        cfg.attributes["connection"] = conn
        command.downgrade(cfg, "base")
    assert _estructura(motor) == {}


def test_verificar_esquema_exige_la_ultima_revision(motor):
    with pytest.raises(RuntimeError, match="alembic"):
        verificar_esquema(motor)  # BD vacía: sin revisión
    _migrar(motor)
    verificar_esquema(motor)  # al día: no falla


def test_bd_existente_con_stamp_head(motor):
    Base.metadata.create_all(bind=motor)  # BD creada antes con create_all
    with pytest.raises(RuntimeError):
        verificar_esquema(motor)
    cfg = _cfg()
    with motor.begin() as conn:
        cfg.attributes["connection"] = conn
        command.stamp(cfg, "head")
    verificar_esquema(motor)
