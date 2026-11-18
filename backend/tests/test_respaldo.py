"""Entrega 14: copia de seguridad y restauración de la base SQLite (RNF-12)."""
import hashlib
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts"))

import respaldo  # noqa: E402
import restaurar  # noqa: E402
from respaldo import ErrorRespaldo  # noqa: E402


def _base_minima(ruta: Path, usuarios=("Ñandú Quispe", "Zoila Huamán")) -> Path:
    """Base sintética con las tablas propias de la plataforma, restricciones y tildes."""
    con = sqlite3.connect(ruta)
    con.executescript(
        """
        CREATE TABLE usuarios (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL, correo TEXT NOT NULL UNIQUE);
        CREATE TABLE desafios (id INTEGER PRIMARY KEY, titulo TEXT NOT NULL);
        CREATE TABLE sesiones (id INTEGER PRIMARY KEY, usuario_id INTEGER NOT NULL REFERENCES usuarios(id),
                               desafio_id INTEGER NOT NULL REFERENCES desafios(id));
        CREATE INDEX ix_sesiones_usuario ON sesiones(usuario_id);
        """
    )
    for i, n in enumerate(usuarios, 1):
        con.execute("INSERT INTO usuarios (nombre, correo) VALUES (?, ?)", (n, f"u{i}@uni.edu"))
    con.execute("INSERT INTO desafios (titulo) VALUES ('Citas del día')")
    con.execute("INSERT INTO sesiones (usuario_id, desafio_id) VALUES (1, 1)")
    con.commit()
    con.close()
    return ruta


def _filas(ruta: Path, sql: str) -> list:
    con = sqlite3.connect(f"{ruta.resolve().as_uri()}?mode=ro", uri=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _huella(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


SQL_USUARIOS = "SELECT * FROM usuarios ORDER BY id"
SQL_ESQUEMA = "SELECT type, name, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name"


def _ida_y_vuelta(origen: Path, tmp_path: Path) -> None:
    """Respalda `origen`, lo daña en una copia de trabajo y comprueba que restaurar devuelve el estado original."""
    antes = _filas(origen, SQL_USUARIOS)
    assert len(antes) >= 1

    copia = respaldo.respaldar(origen, tmp_path / "respaldos")
    assert copia.is_file() and copia.suffix == ".db"
    assert _filas(copia, SQL_USUARIOS) == antes
    assert _filas(copia, SQL_ESQUEMA) == _filas(origen, SQL_ESQUEMA)  # tablas, índices y restricciones
    assert respaldo.verificar_copia(copia)["usuarios"] == len(antes)

    vivo = tmp_path / "vivo.db"
    shutil.copy(origen, vivo)
    con = sqlite3.connect(vivo)  # simula la pérdida de datos
    con.execute("DELETE FROM usuarios")
    con.commit()
    con.close()
    assert _filas(vivo, SQL_USUARIOS) == []

    seguridad = restaurar.restaurar(copia, vivo, tmp_path / "seguridad")
    assert _filas(vivo, SQL_USUARIOS) == antes
    assert _filas(vivo, SQL_ESQUEMA) == _filas(origen, SQL_ESQUEMA)
    assert seguridad is not None and seguridad.name.startswith("antes_de_restaurar_")
    assert _filas(seguridad, SQL_USUARIOS) == []  # la base dañada quedó guardada por si se necesita
    assert not list(tmp_path.glob("*.restaurando")) and not list((tmp_path / "respaldos").glob("*.parcial"))


def test_ida_y_vuelta_con_la_base_real(client, tmp_path):
    from app.core.db import engine
    from conftest import registrar

    assert registrar(client, "Ana Pérez", "ana@uni.edu").status_code in (200, 201)
    _ida_y_vuelta(Path(engine.url.database), tmp_path)


def test_ida_y_vuelta_con_base_sintetica(tmp_path):
    _ida_y_vuelta(_base_minima(tmp_path / "origen.db"), tmp_path)


def test_el_respaldo_no_modifica_el_origen(tmp_path):
    origen = _base_minima(tmp_path / "origen.db")
    antes = _huella(origen)
    respaldo.respaldar(origen, tmp_path / "r")
    assert _huella(origen) == antes
    assert not list(tmp_path.glob("origen.db-*"))


def test_respaldo_con_otra_conexion_escribiendo(tmp_path):
    """Con una transacción sin confirmar en el origen, la copia contiene solo lo confirmado."""
    origen = _base_minima(tmp_path / "origen.db")
    escritor = sqlite3.connect(origen, isolation_level=None)
    escritor.execute("BEGIN IMMEDIATE")
    escritor.execute("INSERT INTO usuarios (nombre, correo) VALUES ('Pendiente', 'p@uni.edu')")
    try:
        copia = respaldo.respaldar(origen, tmp_path / "r")
    finally:
        escritor.execute("ROLLBACK")
        escritor.close()
    assert [f[1] for f in _filas(copia, SQL_USUARIOS)] == ["Ñandú Quispe", "Zoila Huamán"]


def test_dos_copias_en_el_mismo_segundo_no_se_pisan(tmp_path):
    origen = _base_minima(tmp_path / "origen.db")
    ahora = datetime(2026, 11, 17, 10, 30, 0, tzinfo=timezone.utc)
    a = respaldo.respaldar(origen, tmp_path / "r", ahora=ahora)
    b = respaldo.respaldar(origen, tmp_path / "r", ahora=ahora)
    assert a != b and a.name == "desafios_sql_20261117_103000.db" and a.is_file() and b.is_file()


@pytest.mark.parametrize("caso", ["inexistente", "no_sqlite", "vacia"])
def test_respaldo_rechaza_origenes_invalidos(tmp_path, caso):
    origen = tmp_path / "x.db"
    if caso == "no_sqlite":
        origen.write_bytes(b"esto no es una base de datos " * 50)
    elif caso == "vacia":
        sqlite3.connect(origen).close()
    with pytest.raises(ErrorRespaldo):
        respaldo.respaldar(origen, tmp_path / "r")
    restos = list((tmp_path / "r").glob("*")) if (tmp_path / "r").exists() else []
    assert restos == []  # ni copias ni archivos .parcial


def test_restaurar_rechaza_copia_danada_y_deja_el_destino_intacto(tmp_path):
    vivo = _base_minima(tmp_path / "vivo.db")
    antes = _huella(vivo)
    mala = tmp_path / "mala.db"
    mala.write_bytes(b"basura" * 100)
    with pytest.raises(ErrorRespaldo):
        restaurar.restaurar(mala, vivo, tmp_path / "seg")
    assert _huella(vivo) == antes
    assert not (tmp_path / "seg").exists()


def test_restaurar_rechaza_una_base_ajena(tmp_path):
    ajena = tmp_path / "ajena.db"
    con = sqlite3.connect(ajena)
    con.execute("CREATE TABLE otra_cosa (id INTEGER)")
    con.commit()
    con.close()
    vivo = _base_minima(tmp_path / "vivo.db")
    antes = _huella(vivo)
    with pytest.raises(ErrorRespaldo, match="No parece una base"):
        restaurar.restaurar(ajena, vivo, tmp_path / "seg")
    assert _huella(vivo) == antes


def test_restaurar_en_un_destino_que_no_existe(tmp_path):
    copia = respaldo.respaldar(_base_minima(tmp_path / "origen.db"), tmp_path / "r")
    nuevo = tmp_path / "carpeta_nueva" / "desafios_sql.db"
    assert restaurar.restaurar(copia, nuevo, tmp_path / "seg") is None  # no había base: no hay copia previa
    assert _filas(nuevo, SQL_USUARIOS) == _filas(copia, SQL_USUARIOS)


def test_restaurar_no_deja_restos_de_wal_de_la_base_anterior(tmp_path):
    copia = respaldo.respaldar(_base_minima(tmp_path / "origen.db", ("Solo uno",)), tmp_path / "r")
    vivo = _base_minima(tmp_path / "vivo.db")
    (tmp_path / "vivo.db-wal").write_bytes(b"resto")
    (tmp_path / "vivo.db-shm").write_bytes(b"resto")
    restaurar.restaurar(copia, vivo, tmp_path / "seg")
    assert not (tmp_path / "vivo.db-wal").exists() and not (tmp_path / "vivo.db-shm").exists()
    assert [f[1] for f in _filas(vivo, SQL_USUARIOS)] == ["Solo uno"]


def test_restaurar_no_acepta_que_copia_y_destino_sean_el_mismo(tmp_path):
    base = _base_minima(tmp_path / "vivo.db")
    with pytest.raises(ErrorRespaldo, match="mismo archivo"):
        restaurar.restaurar(base, base, tmp_path / "seg")


def test_cli_restaurar_pide_confirmacion(tmp_path, monkeypatch, capsys):
    copia = respaldo.respaldar(_base_minima(tmp_path / "origen.db", ("Del respaldo",)), tmp_path / "r")
    vivo = _base_minima(tmp_path / "vivo.db")
    antes = _huella(vivo)
    argv = [str(copia), "--destino", str(vivo), "--seguridad", str(tmp_path / "seg")]

    monkeypatch.setattr("builtins.input", lambda *_: "no")
    assert restaurar.main(argv) == 2
    assert _huella(vivo) == antes and "No se restauró nada" in capsys.readouterr().out

    def _sin_entrada(*_):
        raise EOFError

    monkeypatch.setattr("builtins.input", _sin_entrada)  # p. ej. sin terminal interactiva
    assert restaurar.main(argv) == 2 and _huella(vivo) == antes

    monkeypatch.setattr("builtins.input", lambda *_: "SI")
    assert restaurar.main(argv) == 0
    assert [f[1] for f in _filas(vivo, SQL_USUARIOS)] == ["Del respaldo"]
    assert "Restauración completa" in capsys.readouterr().out


def test_cli_con_la_base_configurada(client, tmp_path):
    """El script sin --bd usa DATABASE_URL, la misma base que la aplicación."""
    from conftest import registrar

    registrar(client, "Luz Ríos", "luz@uni.edu")
    r = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "respaldo.py"), "--salida", str(tmp_path / "cli")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert r.returncode == 0, r.stderr
    copias = list((tmp_path / "cli").glob("desafios_sql_*.db"))
    assert len(copias) == 1
    assert "luz@uni.edu" in [f[2] for f in _filas(copias[0], SQL_USUARIOS)]
    assert "datos personales" in r.stdout  # el aviso de no subir la copia al repositorio


def test_cli_respaldo_informa_los_errores_en_espanol(tmp_path):
    r = subprocess.run(
        [sys.executable, str(RAIZ / "scripts" / "respaldo.py"), "--bd", str(tmp_path / "no_existe.db"),
         "--salida", str(tmp_path / "r")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert r.returncode == 1 and "No existe" in r.stderr and "Traceback" not in r.stderr


def test_las_copias_y_exportaciones_no_se_suben_al_repositorio():
    ignorado = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "respaldos/" in ignorado and "exportacion_tesis/" in ignorado
    empaque = (RAIZ / "scripts" / "empaquetar.py").read_text(encoding="utf-8")
    assert '"respaldos"' in empaque and '"exportacion_tesis"' in empaque
