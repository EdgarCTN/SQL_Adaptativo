"""Verifica el proyecto: pytest del backend y, si existe frontend/, npm run build."""
import os
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONUTF8": "1"}


def paso(nombre: str, cmd, cwd: Path, shell: bool = False) -> bool:
    print(f"\n=== {nombre} ===", flush=True)
    try:
        ok = subprocess.run(cmd, cwd=cwd, shell=shell, env=ENV).returncode == 0
    except OSError as e:
        print(f"No se pudo ejecutar el paso: {e}")
        ok = False
    print(f"[{'OK' if ok else 'FALLÓ'}] {nombre}", flush=True)
    return ok


def main() -> int:
    resultados = {"Pruebas del backend (pytest)": paso(
        "Pruebas del backend (pytest)", [sys.executable, "-m", "pytest"], RAIZ / "backend"
    )}
    frontend = RAIZ / "frontend"
    if frontend.is_dir():
        if not (frontend / "node_modules").is_dir():
            print("\nAviso: falta frontend/node_modules; ejecuta 'npm install' en frontend/.")
        resultados["Compilación del frontend (npm run build)"] = paso(
            "Compilación del frontend (npm run build)", "npm run build", frontend, shell=True
        )
    print("\n=== Resumen ===")
    for nombre, ok in resultados.items():
        print(f"[{'OK' if ok else 'FALLÓ'}] {nombre}")
    return 0 if all(resultados.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
