# Desafíos SQL adaptativos (MVP del estudiante)

Plataforma web (proyecto de tesis) donde el estudiante se registra, acepta el consentimiento, responde un diagnóstico, resuelve desafíos de SQL en un sandbox, pide ayuda cuando la necesita y ve cómo el sistema ajusta su **nivel de soporte (NS 0 a 3)** por concepto. Hay una pantalla de progreso. El motor de reglas decide el nivel y el tipo de ayuda; el LLM solo redacta. Sin API key funciona en **modo demostración**.

No incluye (aún): rol docente, reportes, Redis ni Docker.

## Requisitos

- Python 3.11 a 3.13 (no 3.14)
- Node 20 o superior
- Git (en Windows, Git Bash)

## Instalación (Git Bash)

```bash
git clone https://github.com/EdgarCTN/SQL_Adaptativo.git
cp .env.example .env

# Backend
cd backend
python -m venv .venv
source .venv/Scripts/activate        # en Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cd ..
python scripts/reset_db.py           # crea la BD y siembra conceptos, 6 desafíos, cuestionario y usuario demo

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
- Puedes registrar tu propia cuenta. El primer ingreso lleva al consentimiento y al diagnóstico.
- `python scripts/reset_db.py` borra y recrea la BD (detén antes el servidor).

## Pruebas

Con el entorno virtual activo, desde la raíz:

```bash
python scripts/verificar.py
```

Ejecuta `pytest` del backend y `npm run build` del frontend (requiere `npm install` previo) e imprime OK o FALLÓ por paso. Solo el backend: `cd backend && python -m pytest`.

## Activar el LLM real

Por defecto `LLM_PROVIDER=mock`: la ayuda sale de las ayudas de respaldo de cada desafío y se rotula como demostración. Para usar Anthropic, edita `.env`:

```
LLM_PROVIDER=anthropic
LLM_MODEL=claude-haiku-5-5
ANTHROPIC_API_KEY=tu-clave
```

Reinicia el servidor. Si falta la clave, la llamada falla o la respuesta no es válida, el estudiante recibe la ayuda de respaldo sin ver errores técnicos. `AnthropicProvider` aún no se ha probado contra la API real. `openai` no está implementado (cae al modo demostración). Temperatura, tokens y tiempos están en `backend/app/config/llm.json`.

## Variables de `.env`

`DATABASE_URL`, `SECRET_KEY` (vacía = clave temporal; las sesiones se pierden al reiniciar), `ACCESS_TOKEN_EXPIRE_MINUTES`, `CORS_ORIGINS`, `DOMINIO_INSTITUCIONAL`, `SEED_USUARIO_DEMO`, `DEMO_EMAIL`, `DEMO_PASSWORD`, `SANDBOX_TIEMPO_MAX_SEG`, `SANDBOX_MAX_FILAS`, `LLM_PROVIDER`, `LLM_MODEL`, `ANTHROPIC_API_KEY`. Cada una está comentada en `.env.example`. El frontend usa `VITE_API_URL` (por defecto `http://localhost:8000/api/v1`; ver `frontend/.env.example`).

## Estructura

```
backend/app/   core/ (config, db, errores, seguridad) · modules/ (auth, linea_base, desafios,
               asistencia, motor_retiro, progreso) · seeds/ · config/ (reglas.json y textos del LLM)
backend/tests/ · frontend/src/ (app, components, features, api) · scripts/
```

Los umbrales de la Matriz de reglas están en `backend/app/config/reglas.json` y se calibran con el piloto. Las decisiones y simplificaciones del MVP están en `DECISIONES.md`.
