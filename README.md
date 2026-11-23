# Desafíos SQL adaptativos

Plataforma web (proyecto de tesis) donde el estudiante se registra, acepta el consentimiento, responde un diagnóstico, resuelve desafíos de SQL en un sandbox, pide ayuda cuando la necesita y ve cómo el sistema ajusta su **nivel de soporte (NS 0 a 3)** por concepto. Hay notificaciones con campana y una pantalla de progreso con resumen, gráficos de evolución de los indicadores y del nivel de ayuda, e historial de intentos con filtros. El motor de reglas (retiro con la preferencia del estudiante, refuerzo, estancamiento, recaída, cambio de dificultad e inactividad) decide el nivel y el tipo de ayuda; el LLM solo redacta. Sin API key funciona en **modo demostración**.

El docente (y el administrador) gestiona un banco de desafíos con validación automática en el sandbox. El administrador asigna roles y activa o desactiva cuentas en «Usuarios», con auditoría de los cambios. Docentes y administradores ven reportes agregados y seudonimizados y pueden descargar los datos para la tesis. No usa Redis. Docker solo se ofrece para un PostgreSQL local de desarrollo (`docker-compose.yml`); el despliegue no usa Docker.

**Manuales:** [estudiante](docs/manual_estudiante.md) · [docente](docs/manual_docente.md) · [administrador](docs/manual_administrador.md). **Antes del piloto:** [pruebas manuales](docs/PRUEBAS_MANUALES.md), [prueba de usabilidad](docs/PRUEBA_USABILIDAD.md) y [valores provisionales](docs/PROVISIONALES.md).

**Despliegue gratuito (Neon + Render + Vercel):** [docs/DESPLIEGUE.md](docs/DESPLIEGUE.md). **Migraciones:** [docs/MIGRACIONES.md](docs/MIGRACIONES.md).

## Requisitos

- Python 3.11 a 3.13 (no 3.14)
- Node 20 o superior
- Git (en Windows, Git Bash)
- Opcional: Docker (solo para un PostgreSQL local) y los clientes de PostgreSQL `pg_dump`/`pg_restore` (solo para respaldar PostgreSQL)

## Instalación (Git Bash)

```bash
git clone https://github.com/EdgarCTN/SQL_Adaptativo.git && cd SQL_Adaptativo
cp .env.example .env

# Backend
cd backend
python -m venv .venv
source .venv/Scripts/activate        # en Linux/macOS: source .venv/bin/activate
pip install -r requirements-dev.txt   # producción + pytest; en un servidor basta requirements.txt
cd ..
python scripts/reset_db.py           # crea la BD y siembra conceptos (con prerrequisitos), 16 desafíos, cuestionario y usuario demo

# Frontend
cd frontend
npm install
cd ..
```

Si `python` no responde pero `py` sí, usa `py`. Para evitar problemas de codificación: `export PYTHONUTF8=1`.

## Ejecutar

Abre dos terminales en la raíz del proyecto.

```bash
# Terminal 1: API (http://localhost:8000, documentación en /docs)
cd backend && source .venv/Scripts/activate && uvicorn app.main:app --reload --port 8000
```

```bash
# Terminal 2: interfaz (http://localhost:5173)
cd frontend && npm run dev
```

- Usuario demo: `estudiante@demo.edu` / `Demo12345!` (definido en `.env.example`; se crea si `SEED_USUARIO_DEMO=true`).
- Docente de pruebas (opcional): define `DOCENTE_EMAIL` y `DOCENTE_PASSWORD` en `.env` y reinicia el servidor; vacíos = no se crea. Entra al «Banco de desafíos».
- Primer administrador (opcional): define `ADMIN_EMAIL` y `ADMIN_PASSWORD` en `.env` y reinicia el servidor; vacíos = no se crea, y una cuenta ya existente no se asciende. Entra a «Usuarios» para convertir cuentas en docentes.
- Puedes registrar tu propia cuenta. El primer ingreso lleva al consentimiento y al diagnóstico.
- En **desarrollo** `create_all` crea las tablas nuevas al arrancar, pero no añade columnas a tablas existentes. Si una entrega indica un cambio de esquema (por ejemplo las 1, 4, 6 y 8), ejecuta `python scripts/reset_db.py`, que borra los datos de desarrollo. En **producción** el esquema lo crea y actualiza Alembic (`alembic upgrade head`; ver [docs/MIGRACIONES.md](docs/MIGRACIONES.md)).
- `python scripts/reset_db.py` borra y recrea la BD (detén antes el servidor). Se niega a ejecutarse con `ENTORNO=produccion` o con una base en un host que no sea local.

### PostgreSQL local (opcional)

Por defecto el desarrollo usa SQLite. Para probar con PostgreSQL (el motor de producción):

```bash
bash scripts/bd.sh todo      # levanta PostgreSQL 18, migra, siembra los datos iniciales y verifica que todo funciona
```

`scripts/bd.sh` fija la URL de la base local por sí mismo, así que no depende de tu `.env`. Para que la **app** (uvicorn) use esa base, cambia en `.env`:
`DATABASE_URL=postgresql+psycopg://sqladaptativo:sqladaptativo_dev@127.0.0.1:5433/sql_adaptativo`. Otros comandos (`bd.sh ayuda`): `psql`, `probar`, `pruebas`, `reiniciar`, `neon-probar`. Guía completa en [docs/PRUEBA_BASE_DE_DATOS.md](docs/PRUEBA_BASE_DE_DATOS.md).

El sandbox de los desafíos y la validación del docente siguen usando SQLite en memoria aunque la base de la app sea PostgreSQL.

## Pruebas

Con el entorno virtual activo, desde la raíz:

```bash
python scripts/verificar.py
```

Ejecuta `pytest` del backend (más de 940 pruebas; tarda varios minutos con SQLite) y `npm run build` del frontend (requiere `npm install` previo) e imprime OK o FALLÓ por paso. Solo el backend: `cd backend && python -m pytest`.

Las pruebas también pueden correr contra PostgreSQL local con `TEST_DATABASE_URL` (variable de entorno; solo se aceptan hosts locales porque las pruebas **borran las tablas**). Las pruebas marcadas `solo_sqlite` se omiten en ese modo; la suite completa tarda mucho más (más de una hora):

```bash
cd backend
TEST_DATABASE_URL=postgresql+psycopg://sqladaptativo:sqladaptativo_dev@127.0.0.1:5433/sql_adaptativo_test python -m pytest -m "not solo_sqlite"
```

El flujo de CI (`.github/workflows/ci.yml`) ejecuta la suite en SQLite, en PostgreSQL con `alembic upgrade head` y `alembic check`, y el `npm run build` del frontend.

## Reportes y exportación para la tesis

Docentes y administradores ven la página «Reportes» (datos agregados, con seudónimos; los grupos de menos de `reportes.n_minimo` estudiantes, 3 por defecto, salen como «Oculto») y pueden descargar CSV seudonimizados de intentos, ayudas, cambios de NS e indicadores. Desde la terminal:

```bash
python scripts/exportar_tesis.py --desde 2026-10-01 --hasta 2026-11-30 --salida exportacion_tesis
```

Define `ANON_SALT` en el `.env` antes de exportar (`python -c "import secrets; print(secrets.token_hex(32))"`); sin ella los seudónimos cambian en cada ejecución. Los CSV están en `.gitignore` (`exportacion_tesis/`): no los subas al repositorio.

## Copias de seguridad

```bash
python scripts/respaldo.py                       # crea respaldos/desafios_sql_AAAAMMDD_HHMMSS.db (SQLite) o .dump (PostgreSQL/Neon)
python scripts/restaurar.py respaldos/<copia>    # con el servidor apagado; guarda antes una copia de la base actual
```

Con SQLite usa `sqlite3`; con PostgreSQL usa `pg_dump`/`pg_restore` y la misma `DATABASE_URL` de la app. **Los clientes de PostgreSQL deben tener la misma versión mayor que el servidor** (Neon incluido). Las copias contienen datos personales: guárdalas fuera del repositorio (`respaldos/` y `*.dump` están ignorados). Detalles en el [manual del administrador](docs/manual_administrador.md) y, para Neon, en [docs/DESPLIEGUE.md](docs/DESPLIEGUE.md#8-respaldos-y-restauración-con-neon).

## Antes de usar con estudiantes

Pon `ENTORNO=produccion` y `SEED_USUARIO_DEMO=false` (la cuenta demo tiene contraseña conocida), define `SECRET_KEY` y `ANON_SALT`, y confirma que el texto del consentimiento (versión 1.1) lo validó tu profesora o el comité. Sigue el checklist de [docs/DESPLIEGUE.md](docs/DESPLIEGUE.md#9-checklist-antes-de-usar-con-estudiantes). Nunca subas `.env` ni claves al repositorio.

## Despliegue

Producción gratuita con **Neon** (PostgreSQL), **Render** (API, `render.yaml`) y **Vercel** (frontend, `frontend/vercel.json`), sin Docker. Guía paso a paso, variables por servicio, límites del plan gratuito (la API se duerme, arranque en frío, suspensión de Neon) y respaldos: [docs/DESPLIEGUE.md](docs/DESPLIEGUE.md).

## Activar el LLM real

Por defecto `LLM_PROVIDER=mock`: la ayuda sale de las ayudas de respaldo de cada desafío y se rotula como demostración. Para usar IA real con **Groq** (modelo `openai/gpt-oss-120b`), edita `.env`:

```
LLM_PROVIDER=groq
GROQ_MODEL=openai/gpt-oss-120b
GROQ_API_KEY=
```

(`GROQ_API_KEY` también se puede definir como variable de entorno.) Instala las dependencias con `pip install -r backend/requirements.txt` y reinicia el servidor. Si falta la clave, el paquete, la llamada falla o la respuesta no es válida, el estudiante recibe la ayuda de respaldo sin ver errores técnicos (el motivo queda en el log del servidor, sin la clave). También están disponibles `LLM_PROVIDER=anthropic` (con `ANTHROPIC_API_KEY` y `LLM_MODEL`) y `LLM_PROVIDER=openai` (con `OPENAI_API_KEY` y `OPENAI_MODEL`). Las respuestas pasan validaciones antes de mostrarse; las ayudas y valoraciones se recuperan desde el servidor después de recargar. Sin clave configurada se usa el modo de demostración. Temperatura, tokens, margen de razonamiento y tiempos están en `backend/app/config/llm.json`.

## Variables de `.env`

`ENTORNO` (`desarrollo` por defecto o `produccion`; en producción la app no arranca sin `SECRET_KEY` ni `ANON_SALT`, ni con SQLite), `DATABASE_URL` (SQLite por defecto; PostgreSQL/Neon en producción), `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE` (pool de PostgreSQL, opcionales), `CREAR_TABLAS_AUTO` (vacío = automático; ver [docs/MIGRACIONES.md](docs/MIGRACIONES.md)), `SECRET_KEY` (en desarrollo, vacía = clave temporal y las sesiones se pierden al reiniciar; en producción es obligatoria), `ACCESS_TOKEN_EXPIRE_MINUTES`, `CORS_ORIGINS`, `DOMINIO_INSTITUCIONAL`, `SEED_USUARIO_DEMO`, `DEMO_EMAIL`, `DEMO_PASSWORD`, `DOCENTE_EMAIL`, `DOCENTE_PASSWORD`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `SANDBOX_TIEMPO_MAX_SEG`, `SANDBOX_MAX_FILAS`, `LLM_PROVIDER`, `LLM_MODEL`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `GROQ_MODEL`, `OPENAI_API_KEY`, `OPENAI_MODEL` y `ANON_SALT` (sal de los seudónimos; opcional en desarrollo, obligatoria en producción y sin cambiarla después). `APP_NOMBRE` y `API_PREFIX` existen en la configuración pero no se cambian: el frontend asume `/api/v1`. Cada una está comentada en `.env.example`. El frontend usa `VITE_API_URL` (por defecto `http://localhost:8000/api/v1`; ver `frontend/.env.example`). Qué variable va en cada servicio (Render, Vercel): [docs/DESPLIEGUE.md](docs/DESPLIEGUE.md#6-variables-por-servicio).

## Estructura

```
backend/app/   core/ (config, db, errores, seguridad) · modules/ (auth, linea_base, desafios,
               asistencia, motor_retiro, ajustes, analitica, notificaciones, progreso, docente, admin,
               reportes) · seeds/ ·
               config/ (reglas.json y textos del LLM)
backend/alembic/ (migraciones) · backend/tests/ · frontend/src/ (app, components, features, api)
scripts/       reset_db, verificar, empaquetar, exportar_tesis, respaldo, restaurar, contexto, probar_groq
docs/          manuales, DESPLIEGUE, MIGRACIONES, TRAZABILIDAD, referencia/ y documentos de proceso
render.yaml (API en Render) · frontend/vercel.json · docker-compose.yml (solo PostgreSQL local)
.github/workflows/ci.yml · .env.example
```

Los umbrales de la Matriz de reglas están en `backend/app/config/reglas.json` y se calibran con el piloto. Las decisiones y simplificaciones del MVP están en [docs/DECISIONES.md](docs/DECISIONES.md).

**Documentos de proceso** (cómo se construyó el proyecto por entregas): [docs/HOJA_DE_RUTA.md](docs/HOJA_DE_RUTA.md), [docs/ENTREGAS.md](docs/ENTREGAS.md), [docs/CONTEXTO_BASE.md](docs/CONTEXTO_BASE.md) y [docs/TRAZABILIDAD.md](docs/TRAZABILIDAD.md). `python scripts/probar_groq.py` hace una llamada real de prueba al proveedor de IA configurado.
