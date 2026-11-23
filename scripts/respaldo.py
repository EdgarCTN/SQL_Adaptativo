"""Copia de seguridad de la base de datos (RNF-12): SQLite (desarrollo) o PostgreSQL/Neon (producción).

Uso (desde la raíz del proyecto):
    python scripts/respaldo.py                       # copia en ./respaldos/desafios_sql_AAAAMMDD_HHMMSS.db
    python scripts/respaldo.py --salida D:/copias    # otra carpeta
    python scripts/respaldo.py --bd ruta/otra.db     # otra base (por defecto, la de DATABASE_URL)

Qué hace según DATABASE_URL (la misma que usa la aplicación):
  - SQLite: `sqlite3.Connection.backup` (imagen consistente aunque haya escrituras) y `PRAGMA integrity_check`.
    Genera desafios_sql_AAAAMMDD_HHMMSS.db
  - PostgreSQL: `pg_dump --format=custom` y verificación con `pg_restore --list`. Genera ...AAAAMMDD_HHMMSS.dump
    Requiere los clientes de PostgreSQL (pg_dump/pg_restore) de versión >= la del servidor. La clave viaja en
    PGPASSWORD, nunca en la línea de comandos. Con Neon, un host «-pooler» se cambia por el directo (pg_dump
    no funciona bien a través de PgBouncer).
Para volver atrás: `python scripts/restaurar.py <copia>`.

La copia contiene datos personales (nombres, correos, código SQL de los estudiantes): guárdala fuera del
repositorio (la carpeta `respaldos/` está en `.gitignore`) y bórrala cuando termine la validación.
"""
import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CARPETA_POR_DEFECTO = RAIZ / "respaldos"
PREFIJO = "desafios_sql"
# Tablas que toda base de esta plataforma tiene; sirven para no restaurar un archivo ajeno por error.
TABLAS_ESPERADAS = ("usuarios", "desafios")
EXT_PG = ".dump"  # copias de PostgreSQL (pg_dump formato custom)
CABECERA_DUMP_PG = b"PGDMP"  # primeros bytes de todo archivo de pg_dump --format=custom
TIMEOUT_PG_SEG = 900


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
            "DATABASE_URL no apunta a un archivo SQLite (con PostgreSQL el script usa pg_dump, sin --bd)."
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


def _nombre_libre(carpeta: Path, prefijo: str, ahora: datetime, extension: str = ".db") -> Path:
    base = f"{prefijo}_{ahora:%Y%m%d_%H%M%S}"
    destino = carpeta / f"{base}{extension}"
    n = 2
    while destino.exists():
        destino = carpeta / f"{base}_{n}{extension}"
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


# ----------------------------------------------------------------------------------------------
# PostgreSQL (Neon): pg_dump / pg_restore
# ----------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class ConexionPG:
    host: str
    base: str
    puerto: int | None = None
    usuario: str | None = None
    clave: str | None = field(default=None, repr=False)  # nunca se imprime
    opciones: dict = field(default_factory=dict)  # sslmode, channel_binding... de la cadena de conexión
    era_pooler: bool = False  # el host de la URL era el del pooler de Neon

    @property
    def descripcion(self) -> str:
        return f"{self.base} en {self.host}"


def url_configurada():
    """URL de SQLAlchemy de DATABASE_URL (la misma que usa la aplicación)."""
    sys.path.insert(0, str(RAIZ / "backend"))
    from sqlalchemy.engine import make_url

    from app.core.config import settings

    return make_url(settings.database_url)


def es_postgres(url) -> bool:
    return url.drivername.startswith("postgresql")


def conexion_pg(url) -> ConexionPG:
    """Convierte una URL de SQLAlchemy (o algo con los mismos atributos) en los datos para pg_dump/pg_restore."""
    if not url.database:
        raise ErrorRespaldo("DATABASE_URL no indica el nombre de la base de datos.")
    host = url.host or "localhost"
    etiqueta, _, resto = host.partition(".")
    era_pooler = etiqueta.endswith("-pooler")
    if era_pooler:  # Neon: pg_dump/pg_restore necesitan la conexión directa, no la de PgBouncer
        host = etiqueta[: -len("-pooler")] + ("." + resto if resto else "")
    opciones = {k: (v if isinstance(v, str) else v[-1]) for k, v in dict(url.query).items()}
    return ConexionPG(host, url.database, url.port, url.username, url.password, opciones, era_pooler)


_OPCION_A_ENTORNO_PG = {"sslmode": "PGSSLMODE", "channel_binding": "PGCHANNELBINDING", "sslrootcert": "PGSSLROOTCERT"}


def entorno_pg(c: ConexionPG) -> dict[str, str]:
    env = dict(os.environ)
    if c.clave:
        env["PGPASSWORD"] = c.clave
    for opcion, variable in _OPCION_A_ENTORNO_PG.items():
        if c.opciones.get(opcion):
            env[variable] = str(c.opciones[opcion])
    env["PGCONNECT_TIMEOUT"] = "30"  # Neon puede tardar unos segundos en despertar
    return env


def args_conexion_pg(c: ConexionPG) -> list[str]:
    """Argumentos de conexión SIN la clave (esa va en PGPASSWORD)."""
    args = ["-h", c.host]
    if c.puerto:
        args += ["-p", str(c.puerto)]
    if c.usuario:
        args += ["-U", c.usuario]
    return args + ["-d", c.base]


def _exigir_herramienta(nombre: str) -> str:
    ruta = shutil.which(nombre)
    if not ruta:
        raise ErrorRespaldo(
            f"No se encontró '{nombre}'. Instala los clientes de PostgreSQL (versión igual o mayor que la del "
            "servidor; Neon admite 16, 17 y 18) y comprueba que estén en el PATH."
        )
    return ruta


def _ejecutar(cmd: list[str], env: dict[str, str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT_PG_SEG
        )
    except subprocess.TimeoutExpired as e:
        raise ErrorRespaldo(f"{Path(cmd[0]).name} tardó más de {TIMEOUT_PG_SEG // 60} minutos y se canceló.") from e
    except OSError as e:
        raise ErrorRespaldo(f"No se pudo ejecutar {Path(cmd[0]).name}: {e}") from e


def _cola(texto: str, n: int = 400) -> str:
    texto = (texto or "").strip()
    return texto[-n:] if texto else "(sin detalle)"


def es_dump_pg(ruta: Path) -> bool:
    try:
        with open(ruta, "rb") as f:
            return f.read(len(CABECERA_DUMP_PG)) == CABECERA_DUMP_PG
    except OSError:
        return False


def verificar_dump_pg(ruta: Path, *, exigir_tablas: bool = True) -> set[str]:
    """Comprueba que `ruta` sea un dump legible (pg_restore --list) y devuelve las tablas con datos."""
    if not ruta.is_file():
        raise ErrorRespaldo(f"No existe el archivo: {ruta}")
    if not es_dump_pg(ruta):
        raise ErrorRespaldo(f"No es una copia de PostgreSQL hecha con pg_dump --format=custom: {ruta}")
    r = _ejecutar([_exigir_herramienta("pg_restore"), "--list", str(ruta)], dict(os.environ))
    if r.returncode != 0:
        raise ErrorRespaldo(f"La copia está dañada o es de una versión no soportada ({_cola(r.stderr)}): {ruta}")
    tablas = set()
    for linea in r.stdout.splitlines():
        m = re.search(r"\bTABLE DATA\s+(\S+)\s+(\S+)", linea)
        if m:
            tablas.add(m.group(2))
    if exigir_tablas:
        faltan = [t for t in TABLAS_ESPERADAS if t not in tablas]
        if faltan:
            raise ErrorRespaldo(
                f"No parece una base de Desafíos SQL (faltan las tablas: {', '.join(faltan)}): {ruta}"
            )
    return tablas


def respaldar_postgres(
    c: ConexionPG, carpeta: Path, *, prefijo: str = PREFIJO, ahora: datetime | None = None, exigir_tablas: bool = True
) -> Path:
    """Crea una copia verificada (.dump) de la base PostgreSQL `c` dentro de `carpeta` y devuelve su ruta."""
    exe = _exigir_herramienta("pg_dump")
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = _nombre_libre(carpeta, prefijo, ahora or datetime.now(timezone.utc), EXT_PG)
    parcial = destino.with_name(destino.name + ".parcial")
    parcial.unlink(missing_ok=True)
    cmd = [exe, "--format=custom", "--no-owner", "--no-privileges", "--file", str(parcial), *args_conexion_pg(c)]
    try:
        r = _ejecutar(cmd, entorno_pg(c))
        if r.returncode != 0:
            raise ErrorRespaldo(f"pg_dump falló ({_cola(r.stderr)})")
        verificar_dump_pg(parcial, exigir_tablas=exigir_tablas)
        os.replace(parcial, destino)  # la copia solo aparece con su nombre final cuando está completa
    except OSError as e:
        raise ErrorRespaldo(f"No se pudo crear la copia: {e}") from e
    finally:
        parcial.unlink(missing_ok=True)
    try:
        os.chmod(destino, 0o600)
    except OSError:
        pass
    return destino


def _main_postgres(salida: Path) -> int:
    c = conexion_pg(url_configurada())
    if c.era_pooler:
        print(f"Aviso: el host era el pooler de Neon; se usa la conexión directa ({c.host}).")
    print(f"Respaldando {c.descripcion} (pg_dump)...", flush=True)
    copia = respaldar_postgres(c, salida)
    tablas = verificar_dump_pg(copia)
    print(f"Copia creada: {copia}  ({copia.stat().st_size / 1024:.0f} KB, {len(tablas)} tablas con datos, verificada)")
    print("Aviso: la copia contiene datos personales. Guárdala fuera del repositorio.")
    print(f'Para restaurarla: python scripts/restaurar.py "{copia}"')
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Copia de seguridad de la base de la plataforma (SQLite o PostgreSQL).")
    ap.add_argument("--bd", help="archivo SQLite a respaldar (por defecto, la base de DATABASE_URL: SQLite o PostgreSQL)")
    ap.add_argument("--salida", default=str(CARPETA_POR_DEFECTO), help="carpeta de destino (se crea si no existe)")
    args = ap.parse_args(argv)
    try:
        if not args.bd and es_postgres(url_configurada()):
            return _main_postgres(Path(args.salida))
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
