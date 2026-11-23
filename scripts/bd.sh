#!/usr/bin/env bash
# Atajos para la base de datos (PostgreSQL 18 en Docker). Úsalo desde Git Bash, en cualquier carpeta del proyecto:
#   bash scripts/bd.sh ayuda
#
# Todos los comandos locales fijan DATABASE_URL por sí mismos (variable de entorno de ese comando), así que
# NO dependen de lo que diga tu .env: no puedes migrar o probar por error contra SQLite.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

USUARIO="sqladaptativo"
CLAVE="sqladaptativo_dev"
BD="sql_adaptativo"
BD_PRUEBAS="sql_adaptativo_test"
PUERTO="${POSTGRES_PORT:-5433}"
URL_DEV="postgresql+psycopg://${USUARIO}:${CLAVE}@127.0.0.1:${PUERTO}/${BD}"
URL_PRUEBAS="postgresql+psycopg://${USUARIO}:${CLAVE}@127.0.0.1:${PUERTO}/${BD_PRUEBAS}"

if command -v python >/dev/null 2>&1; then PY=python; elif command -v py >/dev/null 2>&1; then PY=py; else PY=python3; fi
export PYTHONUTF8=1

# psql dentro del contenedor. Sin argumentos abre la consola interactiva (en Git Bash necesita winpty si existe).
psql_db() {
  local base="$1"; shift
  if [ "$#" -eq 0 ]; then
    if command -v winpty >/dev/null 2>&1 && [[ "$(uname -s)" == MINGW* || "$(uname -s)" == MSYS* ]]; then
      winpty docker compose exec db psql -U "$USUARIO" -d "$base"
    else
      docker compose exec db psql -U "$USUARIO" -d "$base"
    fi
  else
    docker compose exec -T db psql -U "$USUARIO" -d "$base" "$@"
  fi
}

requiere_docker() {
  if ! docker info >/dev/null 2>&1; then
    echo "Docker no responde. Abre Docker Desktop, espera a que indique que el motor está en ejecución y repite el comando."
    exit 1
  fi
}

confirmar() {  # acepta si / SI / Si / sí / s / yes
  local r
  read -rp "Escribe SI para continuar: " r
  case "$(printf '%s' "$r" | tr '[:upper:]' '[:lower:]')" in si|sí|s|yes|y) return 0 ;; *) echo "Cancelado."; return 1 ;; esac
}

esperar_bd() {
  printf "Esperando a PostgreSQL"
  for _ in $(seq 1 40); do
    # -h 127.0.0.1 (TCP) es imprescindible: en el primer arranque la imagen levanta un servidor TEMPORAL solo por socket
    # para ejecutar docker/postgres-init y luego lo reinicia; por socket parecería «listo» antes de tiempo.
    if docker compose exec -T db psql -h 127.0.0.1 -U "$USUARIO" -d "$BD" -tAc "select 1" >/dev/null 2>&1; then echo " listo."; return 0; fi
    printf "."; sleep 1
  done
  echo; echo "PostgreSQL no respondió a tiempo. Mira: docker compose logs db"; return 1
}

pedir_url_neon() {
  if [ -n "${NEON_DATABASE_URL:-}" ]; then URL_NEON="$NEON_DATABASE_URL"; return; fi
  echo "Pega la cadena DIRECTA de Neon (host sin -pooler, con ?sslmode=require). No se mostrará ni se guardará."
  read -rsp "DATABASE_URL de Neon: " URL_NEON; echo
  [ -n "$URL_NEON" ] || { echo "No pegaste ninguna cadena."; exit 1; }
}

cmd_ayuda() {
  cat <<'AYUDA'
Uso: bash scripts/bd.sh <comando>

PostgreSQL local (Docker, puerto 5433):
  up            Levanta PostgreSQL 18 y espera a que esté listo
  version       Muestra la versión del servidor (debe decir PostgreSQL 18.x)
  psql [args]   Consola psql ya conectada a la base correcta (con args: psql -c "select 1")
  migrar        alembic upgrade head + alembic check sobre la base local
  sembrar       Carga los datos iniciales (conceptos, desafíos, cuestionario, usuario demo) sin arrancar la API
  probar        Verifica de punta a punta que la BD funciona (conexión, versión, migraciones, tablas, datos, escritura)
  pruebas       Corre la suite pytest contra PostgreSQL local (crea sql_adaptativo_test si falta)
  reiniciar     BORRA los datos locales y rehace todo: down -v + up + migrar + sembrar + probar
  estado        Resumen rápido: contenedor, versión y tablas
  todo          up + migrar + sembrar + probar (el camino normal para la primera vez)

Neon (te pide la cadena en la terminal, sin escribirla en el historial ni en .env):
  neon-probar   Verifica Neon (solo lectura + insert con rollback)
  neon-migrar   alembic upgrade head contra Neon (pide confirmación)
  Atajo: define NEON_DATABASE_URL en la sesión para no pegarla cada vez.
AYUDA
}

cmd_up() { docker compose up -d db; esperar_bd; }
cmd_version() { psql_db "$BD" -tAc "select version();"; }
cmd_migrar() {
  ( cd backend && DATABASE_URL="$URL_DEV" alembic upgrade head && DATABASE_URL="$URL_DEV" alembic check )
}
cmd_sembrar() {
  ( cd backend && DATABASE_URL="$URL_DEV" ENTORNO=desarrollo "$PY" - <<'PY'
from app.core.db import SessionLocal, cargar_modelos
from app.seeds.seed import sembrar_todo

cargar_modelos()
with SessionLocal() as db:
    sembrar_todo(db)
print("Datos iniciales sembrados (idempotente: se puede repetir).")
PY
  )
}
cmd_probar() { DATABASE_URL="$URL_DEV" ENTORNO=desarrollo "$PY" scripts/probar_bd.py "$@"; }
cmd_pruebas() {
  local existe
  existe="$(psql_db postgres -tAc "select 1 from pg_database where datname='${BD_PRUEBAS}'" | tr -d '[:space:]')"
  if [ "$existe" != "1" ]; then
    echo "Creando la base ${BD_PRUEBAS}..."
    docker compose exec -T db createdb -U "$USUARIO" "$BD_PRUEBAS"
  fi
  ( cd backend && TEST_DATABASE_URL="$URL_PRUEBAS" "$PY" -m pytest -m "not solo_sqlite" "$@" )
}
cmd_reiniciar() {
  echo "Esto BORRA todos los datos de la base local (volumen de Docker)."
  confirmar || exit 0
  docker compose down -v
  cmd_up; cmd_migrar; cmd_sembrar; cmd_probar
}
cmd_estado() {
  docker compose ps db
  cmd_version
  psql_db "$BD" -c "\dt" | tail -n +1 | head -40
}
cmd_todo() { cmd_up; cmd_migrar; cmd_sembrar; cmd_probar; }

cmd_neon_probar() {
  pedir_url_neon
  DATABASE_URL="$URL_NEON" ENTORNO=desarrollo "$PY" scripts/probar_bd.py "$@"
}
cmd_neon_migrar() {
  pedir_url_neon
  case "$URL_NEON" in *-pooler*) echo "AVISO: la cadena tiene «-pooler». Para migrar usa la DIRECTA (sin -pooler)."; ;; esac
  echo "Se ejecutará 'alembic upgrade head' sobre Neon (crea o actualiza tablas; no borra datos)."
  confirmar || exit 0
  ( cd backend && DATABASE_URL="$URL_NEON" ENTORNO=desarrollo alembic upgrade head && DATABASE_URL="$URL_NEON" ENTORNO=desarrollo alembic check )
}

comando="${1:-ayuda}"; shift || true
case "$comando" in up|version|psql|migrar|sembrar|probar|pruebas|reiniciar|estado|todo) requiere_docker ;; esac
case "$comando" in
  ayuda|-h|--help) cmd_ayuda ;;
  up) cmd_up ;;
  version) cmd_version ;;
  psql) psql_db "$BD" "$@" ;;
  migrar) cmd_migrar ;;
  sembrar) cmd_sembrar ;;
  probar) cmd_probar "$@" ;;
  pruebas) cmd_pruebas "$@" ;;
  reiniciar) cmd_reiniciar ;;
  estado) cmd_estado ;;
  todo) cmd_todo ;;
  neon-probar) cmd_neon_probar "$@" ;;
  neon-migrar) cmd_neon_migrar ;;
  *) echo "Comando desconocido: $comando"; echo; cmd_ayuda; exit 1 ;;
esac
