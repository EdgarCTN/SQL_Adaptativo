"""Copia de seguridad de la base de datos SQLite (RNF-12). Se puede hacer con el servidor encendido.

Uso (desde la raíz del proyecto):
    python scripts/respaldo.py                       # copia en ./respaldos/desafios_sql_AAAAMMDD_HHMMSS.db
    python scripts/respaldo.py --salida D:/copias    # otra carpeta
    python scripts/respaldo.py --bd ruta/otra.db     # otra base (por defecto, la de DATABASE_URL)

Usa `sqlite3.Connection.backup`, que copia una imagen consistente aunque haya escrituras en curso, y
verifica la copia (`PRAGMA integrity_check`). Para volver atrás: `python scripts/restaurar.py <copia>`.

La copia contiene datos personales (nombres, correos, código SQL de los estudiantes): guárdala fuera del
repositorio (la carpeta `respaldos/` está en `.gitignore`) y bórrala cuando termine la validación.
"""
import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CARPETA_POR_DEFECTO = RAIZ / "respaldos"
PREFIJO = "desafios_sql"
# Tablas que toda base de esta plataforma tiene; sirven para no restaurar un archivo ajeno por error.
TABLAS_ESPERADAS = ("usuarios", "desafios")


class ErrorRespaldo(Exception):
    """Fallo esperable (se muestra en español, sin traza)."""


def ruta_bd_configurada() -> Path:
    """Ruta del archivo SQLite que indica DATABASE_URL (la misma que usa la aplicación)."""
    sys.path.insert(0, str(RAIZ / "backend"))
    from sqlalchemy.engine import make_url

    from app.core.config import settings

    url = make_url(settings.database_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        raise ErrorRespaldo(
            "DATABASE_URL no apunta a un archivo SQLite. Este script solo respalda SQLite; "
            "con PostgreSQL usa pg_dump."
        )
    return Path(url.database)


def _abrir_lectura(ruta: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"{ruta.resolve().as_uri()}?mode=ro", uri=True)


def resumen(ruta: Path) -> dict[str, int]:
    """Verifica que `ruta` sea una base SQLite íntegra y devuelve {tabla: nº de filas}."""
    if not ruta.is_file():
        raise ErrorRespaldo(f"No existe el archivo: {ruta}")
    try:
        con = _abrir_lectura(ruta)
        try:
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ErrorRespaldo(f"La base está dañada (falló integrity_check): {ruta}")
            tablas = [
                f[0]
                for f in con.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                )
            ]
            return {t: con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tablas}
        finally:
            con.close()
    except sqlite3.DatabaseError as e:
        raise ErrorRespaldo(f"El archivo no es una base SQLite válida ({e}): {ruta}") from e


def verificar_copia(ruta: Path) -> dict[str, int]:
    """Como `resumen`, y además exige las tablas propias de la plataforma."""
    filas = resumen(ruta)
    if not filas:
        raise ErrorRespaldo(f"La base no tiene tablas (está vacía): {ruta}")
    faltan = [t for t in TABLAS_ESPERADAS if t not in filas]
    if faltan:
        raise ErrorRespaldo(
            f"No parece una base de Desafíos SQL (faltan las tablas: {', '.join(faltan)}): {ruta}"
        )
    return filas


def copiar_con_backup(origen: Path, destino: Path) -> None:
    """Copia `origen` en `destino` con la API de respaldo de SQLite (el origen no se modifica)."""
    src = _abrir_lectura(origen)
    dst = sqlite3.connect(str(destino))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def _nombre_libre(carpeta: Path, prefijo: str, ahora: datetime) -> Path:
    base = f"{prefijo}_{ahora:%Y%m%d_%H%M%S}"
    destino = carpeta / f"{base}.db"
    n = 2
    while destino.exists():
        destino = carpeta / f"{base}_{n}.db"
        n += 1
    return destino


def respaldar(
    origen: Path, carpeta: Path, *, prefijo: str = PREFIJO, ahora: datetime | None = None
) -> Path:
    """Crea una copia verificada de `origen` dentro de `carpeta` y devuelve su ruta."""
    if not origen.is_file():
        raise ErrorRespaldo(f"No existe la base de datos: {origen}")
    resumen(origen)  # falla con un mensaje claro si no es SQLite o está dañada
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = _nombre_libre(carpeta, prefijo, ahora or datetime.now(timezone.utc))
    parcial = destino.with_name(destino.name + ".parcial")
    parcial.unlink(missing_ok=True)
    try:
        copiar_con_backup(origen, parcial)
        verificar_copia(parcial)
        os.replace(parcial, destino)  # la copia solo aparece con su nombre final cuando está completa
    except (sqlite3.Error, OSError) as e:
        raise ErrorRespaldo(f"No se pudo crear la copia: {e}") from e
    finally:
        parcial.unlink(missing_ok=True)
    try:
        os.chmod(destino, 0o600)  # solo el dueño (en Windows no tiene efecto)
    except OSError:
        pass
    return destino


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Copia de seguridad de la base SQLite de la plataforma.")
    ap.add_argument("--bd", help="archivo SQLite a respaldar (por defecto, el de DATABASE_URL)")
    ap.add_argument("--salida", default=str(CARPETA_POR_DEFECTO), help="carpeta de destino (se crea si no existe)")
    args = ap.parse_args(argv)
    try:
        origen = Path(args.bd) if args.bd else ruta_bd_configurada()
        copia = respaldar(origen, Path(args.salida))
        filas = verificar_copia(copia)
    except ErrorRespaldo as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(f"Copia creada: {copia}  ({copia.stat().st_size / 1024:.0f} KB, {len(filas)} tablas, verificada)")
    print(f"Usuarios en la copia: {filas.get('usuarios', 0)}")
    print("Aviso: la copia contiene datos personales. Guárdala fuera del repositorio.")
    print(f'Para restaurarla: python scripts/restaurar.py "{copia}"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
