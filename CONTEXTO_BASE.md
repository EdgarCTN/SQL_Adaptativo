# CONTEXTO BASE (se pega al inicio de cada chat, junto con el zip del proyecto)

Continúo un proyecto existente; **no lo reconstruyas**. Es una plataforma web de desafíos de SQL adaptativos asistidos por IA (proyecto de tesis). El estudiante se registra, acepta el consentimiento, responde un diagnóstico, resuelve desafíos en un sandbox SQL, pide ayuda a una IA y el sistema ajusta su **nivel de soporte (NS 0 a 3) por concepto** con una matriz de reglas (R0 a R14). **El motor de reglas decide el nivel y el tipo de ayuda; el LLM solo redacta.**

## Lo que ya funciona (MVP terminado)
Registro y login (JWT) · perfil · consentimiento y diagnóstico con cálculo de NS inicial (R0 parcial) · 16 desafíos con sandbox SQLite (los 10 conceptos con contenido; 6 del MVP + 4 de la entrega 3A + 3 de la 3B + 3 de la 3C, que son segundos desafíos de `filtrado`, `ordenamiento`, `join`, `having`, `subconsulta` y `funciones_ventana`) y prerrequisitos entre conceptos · ayuda AY1 a AY4 con proveedor mock, Groq o Anthropic, validadores V1 y V2 y ayuda de respaldo · motor con las reglas R6, R8, R7, R5, R2, R1 y R4 (retiro acelerado y estancamiento incluidos) · omitir un desafío («Muy fácil» / «Muy difícil») con desafío más básico sugerido y desafío de verificación · pantalla de progreso. Roles `estudiante`, `docente` y `administrador` existen en el modelo, pero solo el estudiante tiene funciones.

## Stack (no cambiarlo)
Backend: Python 3.11 a 3.13, FastAPI, SQLAlchemy 2 síncrono, Pydantic v2, PyJWT, argon2-cffi, pytest + httpx, SQLite. Frontend: React 18, Vite 5, TypeScript, Tailwind 3.4, react-router 6, axios. Carpetas: `backend/app/{core,modules,seeds,config}` (cada módulo con `router.py`, `schemas.py`, `models.py`, `service.py`; los routers solo orquestan) y `frontend/src/{app,components,features,api}`. API bajo `/api/v1`, textos en español, nombres de dominio sin tildes. **No hay Alembic:** si una entrega añade columnas a una tabla que ya existe, dímelo y pídeme ejecutar `python scripts/reset_db.py` (borra los datos de desarrollo). Dependencias nuevas solo si la entrega lo pide (pandas en la 2, recharts en la 11).

## Mi sistema
Windows con Git Bash. Comandos bash con `/`. Toda automatización en Python (nunca `.sh`, `.bat` ni PowerShell). Usa `pathlib` y `encoding='utf-8'`; sin emojis en la salida de scripts. Verificación: `python scripts/verificar.py` (pytest del backend y `npm run build`).

## El proyecto viene adjunto en un zip
Descomprímelo y trata su contenido como la fuente de verdad del estado actual. **No leas todo el proyecto**, para gastar pocos recursos: (1) lee de este zip la sección de la entrega que te indico en `ENTREGAS.md` y los documentos de `docs/referencia/` que esa sección nombre; (2) ejecuta `python scripts/contexto.py <módulos>` (los módulos los indica la entrega) para ver firmas, tablas y endpoints; (3) abre completos **solo** los archivos que vayas a modificar. Si no puedes ejecutar código, lee directamente los archivos de esos módulos. Si el zip no se puede abrir, dímelo y te pegaré la sección y el resumen del código a mano. Si puedes ejecutar `pytest` con las dependencias disponibles, hazlo antes de entregar; si no, no lo intentes ni afirmes que pasó: yo ejecutaré `python scripts/verificar.py`.

## Piezas existentes que debes reutilizar (no reescribir)
`core.db` (Base, get_db, cargar_modelos, UTCDateTime, ahora_utc) · `core.errores.ErrorApp(mensaje, status_code, extra)` · `core.reglas.cargar_reglas()` · `modules.auth.deps` (usuario_actual, requiere_rol) · `motor_retiro` (NivelSoporteService, ContextoRegla, Regla y ResultadoRegla, evaluador, motor.cerrar_desafio y motor.cerrar_omision, indicadores, mensajes, verificacion) · `desafios` (sandbox.evaluar_consulta, hooks.al_cerrar_desafio y hooks.al_omitir_desafio, seeds) · `asistencia` (decision, prompt_builder, validador.VALIDACIONES, cierre, llm/fabrica) · `seeds.seed.sembrar_todo` · frontend: `useCarga`, `EstadoContenedor`, `Toasts`, `DialogoConfirmacion`, `RutaProtegida`, `Layout` (ENLACES por rol), `api/cliente.ts`. Las firmas exactas están en el código del zip (usa `scripts/contexto.py`). **Si necesitas algo que no encuentras, pídemelo; no lo inventes ni reescribas archivos de memoria.**

## Reglas que nunca se rompen
1. La aplicación nunca falla frente al usuario: sin 500, pantallas en blanco, botones muertos ni enlaces rotos. Si algo opcional falla (por ejemplo el LLM), se degrada con un mensaje amable en español.
2. Los umbrales de la Matriz y de `llm.json` viven en `backend/app/config/*.json`, nunca en el código. Si falta un valor que los documentos no definen, agrégalo con `"provisional": true`, anótalo en DECISIONES.md y avísame en una línea.
3. Al LLM nunca se envían nombre, correo, NS ni indicadores de la ventana. Al cliente nunca se devuelven `solucion_referencia`, `ayudas_respaldo`, `sandbox_setup_sql` ni la clave `correcta`. En reportes solo hay seudónimos, nunca nombres ni correos.
4. Ningún secreto en el repositorio: claves solo en `.env`, que se ignora.
5. No rompas lo anterior: todas las pruebas existentes deben seguir pasando.
6. Haz solo lo que pide esta entrega.

## Cómo responder (ahorra espacio)
Archivos nuevos: completos, con su ruta como título. Archivos existentes de más de 60 líneas: solo el bloque cambiado, con archivo, función y «antes → después». Sin resúmenes ni repetir mi contexto; máximo 10 líneas de comentarios en total. Si la entrega es muy grande, **para al final de un archivo**, lista lo que falta y espera `continúa`. No puedes ejecutar código: dame comandos exactos y yo te pego los errores. Si falta información, no me preguntes: déjalo fuera y anótalo en una línea para DECISIONES.md.

## Al terminar cada entrega, entrégame
1. Los archivos creados o modificados, **con su ruta dentro del proyecto** (si puedes crear archivos, créalos y compártelos para que los descargue; si no, bloques de código con la ruta como título), y si debo ejecutar `reset_db.py`.
2. Pruebas automáticas nuevas de lo que hiciste (pytest; las anteriores siguen pasando) y el comando: `python scripts/verificar.py`.
3. Un checklist manual de 3 a 5 pasos para comprobarlo en el navegador.
4. De 2 a 4 líneas para añadir a «Notas de lo hecho» en `HOJA_DE_RUTA.md` (qué quedó y qué nombres nuevos usarán otras entregas).
5. Las filas de `docs/TRAZABILIDAD.md` que cambian (requisito, estado, prueba que lo demuestra) y las líneas nuevas para DECISIONES.md, marcando como PROVISIONAL lo que deba validar mi profesora.
