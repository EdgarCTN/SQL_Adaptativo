# Manual del administrador

El administrador tiene todo lo del docente (**Banco de desafíos**, **Reportes**) y además **Usuarios**. Los comandos se ejecutan en Git Bash desde la raíz del proyecto.

## 1. Puesta en marcha
- Copia `.env.example` a `.env` y completa, como mínimo: `SECRET_KEY` (si queda vacía, las sesiones se pierden al reiniciar), `ANON_SALT` (sal de los seudónimos; **defínela antes de recoger datos** y no la cambies después) y `ADMIN_EMAIL` / `ADMIN_PASSWORD` (crean el primer administrador; una cuenta existente no se asciende).
- Para el piloto pon `SEED_USUARIO_DEMO=false` (si no, existe una cuenta demo con contraseña conocida) y, si corresponde, `DOMINIO_INSTITUCIONAL`.
- API: `cd backend && source .venv/Scripts/activate && uvicorn app.main:app --port 8000` (documentación en `/docs`). Interfaz: `cd frontend && npm run dev` (puerto 5173).
- **IA real:** `LLM_PROVIDER=groq` más `GROQ_API_KEY` (u `anthropic` / `openai` con su clave) y reinicia. Si algo falla, el estudiante recibe la ayuda de respaldo. Las claves solo van en `.env`, nunca en el repositorio.
- `python scripts/reset_db.py` **borra todos los datos**; solo para desarrollo, con el servidor apagado.

## 2. Usuarios
**Usuarios** permite buscar por nombre o correo, filtrar por rol, **Cambiar rol** (Estudiante, Docente, Administrador) y **Activar** / **Desactivar** cuentas. Cada acción pide confirmación.
- No puedes cambiar tu propio rol ni desactivar tu cuenta, y siempre debe quedar un administrador activo.
- Una cuenta desactivada pierde el acceso en su siguiente solicitud; no se borra nada y puede reactivarse.
- El registro público siempre crea estudiantes: así se nombra a los docentes.
- Los cambios de roles y de cuentas, y las acciones sobre el banco y las descargas de datos, quedan en la tabla `auditoria` (sin correos). Aún no hay pantalla para verla.

## 3. Copias de seguridad (RNF-12)
```bash
python scripts/respaldo.py                 # crea respaldos/desafios_sql_AAAAMMDD_HHMMSS.db
python scripts/respaldo.py --salida D:/copias
```
Se puede hacer con el servidor encendido y la copia se verifica sola. Haz una **antes de cada sesión con estudiantes y después de cada una**; para automatizarlo usa el Programador de tareas de Windows con `python scripts/respaldo.py`. Las copias contienen datos personales: guárdalas fuera del repositorio (la carpeta `respaldos/` está ignorada), con acceso restringido, y bórralas al terminar el estudio.

**Restaurar** (apaga antes el servidor):
```bash
python scripts/restaurar.py respaldos/desafios_sql_20261117_103000.db
```
Pide escribir SI, guarda una copia de la base actual como `antes_de_restaurar_…` y reemplaza la base. Restaura copias del mismo esquema: si una entrega pidió `reset_db.py` después de la copia, la copia es del esquema anterior. Haz una prueba de restauración antes del piloto.

## 4. Datos para la tesis
`python scripts/exportar_tesis.py --desde AAAA-MM-DD --hasta AAAA-MM-DD` escribe CSV seudonimizados en `exportacion_tesis/` (los mismos que descarga **Reportes**). Sin `ANON_SALT` el script avisa porque los seudónimos no serían comparables. Los CSV no llevan nombres, correos ni código SQL, pero con pocos estudiantes un seudónimo puede reidentificarse por contexto: consulta al comité.

## 5. Calibración
Los umbrales están en `backend/app/config/reglas.json`; se leen una vez al arrancar, así que **reinicia el servidor** tras editarlos. La lista de valores provisionales y cómo calibrarlos está en `docs/PROVISIONALES.md`.

## 6. Si algo falla
`/api/v1/health` responde `ok` si la API y la base funcionan. Los errores técnicos quedan en la terminal de `uvicorn`, nunca en pantalla del estudiante. Ante una base dañada: apaga el servidor y restaura la última copia.
