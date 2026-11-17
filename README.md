# Desafíos SQL adaptativos (MVP del estudiante)

Plataforma web (proyecto de tesis) donde el estudiante se registra, acepta el consentimiento, responde un diagnóstico, resuelve desafíos de SQL en un sandbox, pide ayuda cuando la necesita y ve cómo el sistema ajusta su **nivel de soporte (NS 0 a 3)** por concepto. Hay notificaciones con campana y una pantalla de progreso con resumen, gráficos de evolución de los indicadores y del nivel de ayuda, e historial de intentos con filtros. El motor de reglas (retiro con la preferencia del estudiante, refuerzo, estancamiento, recaída, cambio de dificultad e inactividad) decide el nivel y el tipo de ayuda; el LLM solo redacta. Sin API key funciona en **modo demostración**.

El docente (y el administrador) gestiona un banco de desafíos con validación automática en el sandbox. El administrador asigna roles y activa o desactiva cuentas en «Usuarios», con auditoría de los cambios. No incluye (aún): reportes agregados, Redis ni Docker.

## Requisitos

- Python 3.11 a 3.13 (no 3.14)
- Node 20 o superior
- Git (en Windows, Git Bash)

## Instalación (Git Bash)

```bash
git clone https://github.com/EdgarCTN/SQL_Adaptativo.git && cd SQL_Adaptativo
cp .env.example .env

# Backend
cd backend
python -m venv .venv
source .venv/Scripts/activate        # en Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
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
- No hay migraciones (sin Alembic): `create_all` crea las tablas nuevas al arrancar, pero no añade columnas a tablas existentes. Si una entrega indica un cambio de esquema (por ejemplo las 1, 4, 6 y 8), ejecuta `python scripts/reset_db.py`, que borra los datos de desarrollo.
- `python scripts/reset_db.py` borra y recrea la BD (detén antes el servidor). Úsalo cuando una entrega lo pida o si quieres eliminar los datos de desarrollo.

## Pruebas

Con el entorno virtual activo, desde la raíz:

```bash
python scripts/verificar.py
```

Ejecuta `pytest` del backend (más de 900 pruebas; tarda varios minutos) y `npm run build` del frontend (requiere `npm install` previo) e imprime OK o FALLÓ por paso. Solo el backend: `cd backend && python -m pytest`.

## Reportes y exportación para la tesis

Docentes y administradores ven la página «Reportes» (datos agregados, con seudónimos; los grupos de menos de `reportes.n_minimo` estudiantes, 3 por defecto, salen como «Oculto») y pueden descargar CSV seudonimizados de intentos, ayudas, cambios de NS e indicadores. Desde la terminal:

```bash
python scripts/exportar_tesis.py --desde 2026-10-01 --hasta 2026-11-30 --salida mis_datos
```

Define `ANON_SALT` en el `.env` antes de exportar (`python -c "import secrets; print(secrets.token_hex(32))"`); sin ella los seudónimos cambian en cada ejecución.

## Activar el LLM real

Por defecto `LLM_PROVIDER=mock`: la ayuda sale de las ayudas de respaldo de cada desafío y se rotula como demostración. Para usar IA real con **Groq** (modelo `openai/gpt-oss-120b`), edita `.env`:

```
LLM_PROVIDER=groq
GROQ_MODEL=openai/gpt-oss-120b
GROQ_API_KEY=
```

(`GROQ_API_KEY` también se puede definir como variable de entorno.) Instala las dependencias con `pip install -r backend/requirements.txt` y reinicia el servidor. Si falta la clave, el paquete, la llamada falla o la respuesta no es válida, el estudiante recibe la ayuda de respaldo sin ver errores técnicos (el motivo queda en el log del servidor, sin la clave). También están disponibles `LLM_PROVIDER=anthropic` (con `ANTHROPIC_API_KEY` y `LLM_MODEL`) y `LLM_PROVIDER=openai` (con `OPENAI_API_KEY` y `OPENAI_MODEL`). Las respuestas pasan validaciones antes de mostrarse; las ayudas y valoraciones se recuperan desde el servidor después de recargar. Sin clave configurada se usa el modo de demostración. Temperatura, tokens, margen de razonamiento y tiempos están en `backend/app/config/llm.json`.

## Variables de `.env`

`DATABASE_URL`, `SECRET_KEY` (vacía = clave temporal; las sesiones se pierden al reiniciar), `ACCESS_TOKEN_EXPIRE_MINUTES`, `CORS_ORIGINS`, `DOMINIO_INSTITUCIONAL`, `SEED_USUARIO_DEMO`, `DEMO_EMAIL`, `DEMO_PASSWORD`, `DOCENTE_EMAIL`, `DOCENTE_PASSWORD`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `SANDBOX_TIEMPO_MAX_SEG`, `SANDBOX_MAX_FILAS`, `LLM_PROVIDER`, `LLM_MODEL`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, `GROQ_MODEL`, `OPENAI_API_KEY`, `OPENAI_MODEL` y `ANON_SALT` (sal de los seudónimos; opcional). Cada una está comentada en `.env.example`. El frontend usa `VITE_API_URL` (por defecto `http://localhost:8000/api/v1`; ver `frontend/.env.example`).

## Estructura

```
backend/app/   core/ (config, db, errores, seguridad) · modules/ (auth, linea_base, desafios,
               asistencia, motor_retiro, ajustes, analitica, notificaciones, progreso, docente) · seeds/ ·
               config/ (reglas.json y textos del LLM)
backend/tests/ · frontend/src/ (app, components, features, api) · scripts/
```

Los umbrales de la Matriz de reglas están en `backend/app/config/reglas.json` y se calibran con el piloto. Las decisiones y simplificaciones del MVP están en `DECISIONES.md`.
