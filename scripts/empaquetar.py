"""Crea proyecto_para_claude.zip para adjuntarlo a un chat de Claude.

Uso (desde la raiz del proyecto, en Git Bash):  python scripts/empaquetar.py

Excluye: .git, node_modules, .venv, __pycache__, .env, bases de datos (*.db),
carpetas de compilacion y otros zip. REVISA ANTES si hay claves en los archivos
que si se incluyen y se niega a crear el zip si encuentra alguna.
"""
import re
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "proyecto_para_claude.zip"
CARPETAS_EXCLUIDAS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache",
                      "dist", "build", ".idea", ".vscode", ".mypy_cache"}
NOMBRES_EXCLUIDOS = {".env"}
EXTENSIONES_EXCLUIDAS = {".db", ".sqlite", ".sqlite3", ".zip", ".pyc", ".log"}
PATRONES_SECRETOS = [
    (r"gsk_[A-Za-z0-9]{20,}", "clave de Groq"),
    (r"sk-ant-[A-Za-z0-9_\-]{20,}", "clave de Anthropic"),
    (r"sk-[A-Za-z0-9]{32,}", "clave tipo OpenAI"),
    (r"AKIA[0-9A-Z]{16}", "clave de AWS"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "llave privada"),
]
LIMITE_ARCHIVO = 1_000_000  # no se incluyen archivos de texto de mas de 1 MB


def incluidos():
    for ruta in sorted(RAIZ.rglob("*")):
        if not ruta.is_file():
            continue
        rel = ruta.relative_to(RAIZ)
        if any(parte in CARPETAS_EXCLUIDAS for parte in rel.parts):
            continue
        if ruta.name in NOMBRES_EXCLUIDOS or ruta.suffix.lower() in EXTENSIONES_EXCLUIDAS:
            continue
        if ruta.stat().st_size > LIMITE_ARCHIVO:
            print(f"  (omitido por tamano: {rel.as_posix()})")
            continue
        yield ruta, rel


def buscar_secretos(ruta: Path):
    try:
        texto = ruta.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    return [desc for patron, desc in PATRONES_SECRETOS if re.search(patron, texto)]


def main():
    archivos = list(incluidos())
    problemas = []
    for ruta, rel in archivos:
        for desc in buscar_secretos(ruta):
            problemas.append((rel.as_posix(), desc))
    if problemas:
        print("NO SE CREO EL ZIP: hay posibles secretos en estos archivos:")
        for rel, desc in problemas:
            print(f"  - {rel}: {desc}")
        print("Borra o deja vacio ese valor, revoca la clave en su consola y vuelve a ejecutar.")
        sys.exit(1)
    if SALIDA.exists():
        SALIDA.unlink()
    with zipfile.ZipFile(SALIDA, "w", zipfile.ZIP_DEFLATED) as z:
        for ruta, rel in archivos:
            z.write(ruta, rel.as_posix())
    tam = SALIDA.stat().st_size / 1024
    print(f"OK: {SALIDA.name} con {len(archivos)} archivos ({tam:.0f} KB). Adjuntalo al chat.")
    print("Recuerda: no subas este zip a GitHub (esta ignorado por .gitignore si agregaste '*.zip').")


if __name__ == "__main__":
    main()
