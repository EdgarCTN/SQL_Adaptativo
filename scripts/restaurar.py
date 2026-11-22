"""Restaura una copia hecha con scripts/respaldo.py (RNF-12): SQLite (.db) o PostgreSQL/Neon (.dump). REEMPLAZA la base actual.

Uso (desde la raíz del proyecto, con el servidor APAGADO):
    python scripts/restaurar.py respaldos/desafios_sql_20261117_103000.db
    python scripts/restaurar.py copia.db --confirmar            # sin preguntar
    python scripts/restaurar.py copia.db --destino otra.db      # restaurar en otro archivo

Antes de tocar nada verifica la copia (`integrity_check`/`pg_restore --list` y tablas propias de la plataforma). Si
ya existía una base, guarda una copia de seguridad suya en ./respaldos con el prefijo «antes_de_restaurar». Si algo
falla, la base actual queda como estaba.

SQLite: después de restaurar, arranca el servidor (en desarrollo `create_all` añade las tablas nuevas que la copia no
tuviera; las columnas nuevas no: si una entrega pidió reset_db.py, la copia es del esquema viejo).
PostgreSQL: se usa `pg_restore --clean --if-exists --single-transaction` (todo o nada) sobre la base de DATABASE_URL.
Pide escribir el NOMBRE de la base para confirmar. Si la copia es de un esquema anterior, ejecuta después
`cd backend && alembic upgrade head` (docs/MIGRACIONES.md). Detén la API (Render) mientras restauras.
"""
import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import respaldo  # noqa: E402  (se usa como respaldo._ejecutar para poder simularlo en pruebas)
from respaldo import (  # noqa: E402
    CARPETA_POR_DEFECTO,
    ConexionPG,
    ErrorRespaldo,
    _cola,
    _exigir_herramienta,
    args_conexion_pg,
    conexion_pg,
    copiar_con_backup,
    entorno_pg,
    es_dump_pg,
    es_postgres,
    respaldar,
    respaldar_postgres,
    ruta_bd_configurada,
    url_configurada,
    verificar_copia,
    verificar_dump_pg,
)

PREFIJO_SEGURIDAD = "antes_de_restaurar"
MSG_BLOQUEADA = (
    "No se pudo reemplazar la base: está en uso. Detén el servidor (uvicorn) y cualquier programa que la tenga "
    "abierta, y vuelve a intentarlo. La base anterior no se modificó."
)


def _guardar_seguridad(destino: Path, carpeta: Path) -> Path:
    """Copia de seguridad de la base actual; si ya está dañada, copia sus bytes tal cual."""
    try:
        return respaldar(destino, carpeta, prefijo=PREFIJO_SEGURIDAD)
    except ErrorRespaldo:
        carpeta.mkdir(parents=True, exist_ok=True)
        ahora = datetime.now(timezone.utc)
        bruta = carpeta / f"{PREFIJO_SEGURIDAD}_{ahora:%Y%m%d_%H%M%S}_sin_verificar.db"
        shutil.copy2(destino, bruta)
        return bruta


def restaurar(copia: Path, destino: Path, carpeta_seguridad: Path = CARPETA_POR_DEFECTO) -> Path | None:
    """Restaura `copia` sobre `destino`. Devuelve la ruta de la copia de seguridad previa (o None si no había base)."""
    verificar_copia(copia)  # antes de tocar nada
    if copia.resolve() == destino.resolve():
        raise ErrorRespaldo("La copia y la base de destino son el mismo archivo.")
    seguridad = _guardar_seguridad(destino, carpeta_seguridad) if destino.is_file() else None
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporal = destino.with_name(destino.name + ".restaurando")
    temporal.unlink(missing_ok=True)
    try:
        copiar_con_backup(copia, temporal)
        verificar_copia(temporal)
        for sufijo in ("-wal", "-shm", "-journal"):  # restos de la base anterior que no deben mezclarse
            Path(str(destino) + sufijo).unlink(missing_ok=True)
        os.replace(temporal, destino)
    except PermissionError as e:
        raise ErrorRespaldo(MSG_BLOQUEADA) from e
    except (sqlite3.Error, OSError) as e:
        raise ErrorRespaldo(f"No se pudo restaurar la copia: {e}") from e
    finally:
        temporal.unlink(missing_ok=True)
    return seguridad


def restaurar_postgres(copia: Path, c: ConexionPG, carpeta_seguridad: Path = CARPETA_POR_DEFECTO) -> Path:
    """Restaura el dump `copia` sobre la base PostgreSQL `c`. Devuelve la copia de seguridad previa."""
    verificar_dump_pg(copia)  # antes de tocar nada
    # Copia de la base actual; si falla (p. ej. no hay conexión) NO se continúa: sin red de seguridad no se reemplaza.
    seguridad = respaldar_postgres(c, carpeta_seguridad, prefijo=PREFIJO_SEGURIDAD, exigir_tablas=False)
    cmd = [
        _exigir_herramienta("pg_restore"), "--clean", "--if-exists", "--no-owner", "--no-privileges",
        "--single-transaction", "--exit-on-error", *args_conexion_pg(c), str(copia),
    ]
    r = respaldo._ejecutar(cmd, entorno_pg(c))
    if r.returncode != 0:
        pista = ""
        if "transaction_timeout" in (r.stderr or "") or "unrecognized configuration parameter" in (r.stderr or ""):
            pista = (
                " PISTA: tus clientes de PostgreSQL (pg_restore) son más nuevos que el servidor y escriben parámetros que "
                "este no conoce. Usa clientes de la MISMA versión mayor que el servidor (p. ej. 16 para un servidor 16) "
                "o crea el servidor con la versión de tus clientes."
            )
        raise ErrorRespaldo(
            f"pg_restore falló; al ser una sola transacción la base quedó como estaba ({_cola(r.stderr)}). "
            f"Copia de seguridad previa: {seguridad}.{pista}"
        )
    return seguridad


def _main_postgres(args, copia: Path, c: ConexionPG) -> int:
    if not es_dump_pg(copia):
        raise ErrorRespaldo(f"DATABASE_URL es PostgreSQL pero la copia no es un .dump de pg_dump: {copia}")
    if c.era_pooler:
        print(f"Aviso: el host era el pooler de Neon; se usa la conexión directa ({c.host}).")
    tablas = verificar_dump_pg(copia)
    print(f"Copia: {copia}  ({len(tablas)} tablas con datos)")
    print(f"Se REEMPLAZARÁ la base PostgreSQL: {c.descripcion}")
    if not args.confirmar:
        print(f"Escribe el nombre de la base ({c.base}) para continuar (detén antes la API):", flush=True)
        try:
            respuesta = input().strip()
        except EOFError:
            respuesta = ""
        if respuesta != c.base:
            print("No se restauró nada. Para omitir la pregunta usa --confirmar.")
            return 2
    seguridad = restaurar_postgres(copia, c, Path(args.seguridad))
    print(f"Copia de seguridad de la base anterior: {seguridad}")
    print("Restauración completa. Si la copia es de un esquema anterior: cd backend && alembic upgrade head")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Restaura una copia de la base (SQLite o PostgreSQL); reemplaza la actual.")
    ap.add_argument("copia", help="archivo creado por scripts/respaldo.py")
    ap.add_argument("--destino", help="base a reemplazar (por defecto, la de DATABASE_URL)")
    ap.add_argument("--confirmar", action="store_true", help="no preguntar antes de reemplazar")
    ap.add_argument("--seguridad", default=str(CARPETA_POR_DEFECTO), help="carpeta de la copia de seguridad previa")
    args = ap.parse_args(argv)
    try:
        copia = Path(args.copia)
        if not args.destino and es_postgres(url_configurada()):
            return _main_postgres(args, copia, conexion_pg(url_configurada()))
        if es_dump_pg(copia):
            raise ErrorRespaldo("La copia es de PostgreSQL (.dump) pero DATABASE_URL apunta a SQLite.")
        destino = Path(args.destino) if args.destino else ruta_bd_configurada()
        filas = verificar_copia(copia)
        print(f"Copia: {copia}  ({len(filas)} tablas, {filas.get('usuarios', 0)} usuarios)")
        print(f"Se reemplazará la base: {destino}")
        if not args.confirmar:
            print("Escribe SI para continuar (el servidor debe estar apagado):", flush=True)
            try:
                respuesta = input().strip().upper()
            except EOFError:
                respuesta = ""
            if respuesta not in ("SI", "SÍ"):
                print("No se restauró nada. Para omitir la pregunta usa --confirmar.")
                return 2
        seguridad = restaurar(copia, destino, Path(args.seguridad))
    except ErrorRespaldo as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if seguridad:
        print(f"Copia de seguridad de la base anterior: {seguridad}")
    print("Restauración completa. Ya puedes arrancar el servidor.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
