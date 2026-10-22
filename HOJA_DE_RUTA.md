# HOJA DE RUTA

**Siguiente entrega: 1**

Este archivo es el tablero del proyecto: dice qué entrega toca, qué módulos debe revisar Claude y qué quedó hecho. Lo actualizas tú al terminar cada entrega; va dentro del zip, así que Claude también lo ve.

## Archivos del proyecto
| Archivo | Ubicación | Uso |
|---|---|---|
| `CONTEXTO_BASE.md` | raíz | Se pega al inicio de cada chat |
| `ENTREGAS.md` | raíz | Texto de cada entrega; Claude lee solo la sección que toca |
| `HOJA_DE_RUTA.md` | raíz | Este tablero |
| `DECISIONES.md` | raíz | Decisiones y valores provisionales a validar con la profesora |
| `scripts/empaquetar.py` | `scripts/` | Crea `proyecto_para_claude.zip` (sin `.env`, `node_modules` ni bases de datos; se niega si encuentra claves) |
| `scripts/contexto.py` | `scripts/` | Resume el código de los módulos que pida la entrega (Claude lo ejecuta; tú solo si usas el método manual) |
| `docs/TRAZABILIDAD.md` | `docs/` | Estado de cada requisito (RF y RNF) y la prueba que lo demuestra |
| `docs/referencia/` | `docs/referencia/` | `matriz_resumen.md`, `prompt_resumen.md`, `requisitos.md` (y `casos_de_uso_resumen.md`, opcional) |

## Antes de empezar (una sola vez, sin Claude)
1. Copia estos archivos al repositorio y borra `ESTADO.md`. Añade `*.zip` a `.gitignore`.
2. Quita la clave de Groq del `README.md` (déjala vacía), **revócala en la consola de Groq** y crea una nueva. Si el repositorio es público, la clave vieja sigue visible en el historial de Git, por eso hay que revocarla.
3. En Ajustes de Claude activa «Ejecución de código y creación de archivos» (necesaria para que abra el zip). Ejecuta `python scripts/verificar.py` en Git Bash. El MVP solo se verificó en Linux; si algo falla en Windows, pega el error en un chat nuevo con `CONTEXTO_BASE.md` antes de seguir.
4. `git add -A && git commit -m "preparar fase 2"`.

## Cómo hacer cada entrega
1. Desde la raíz del proyecto, ejecuta `python scripts/empaquetar.py`. Crea `proyecto_para_claude.zip` (unos cientos de KB). Si encuentra una clave en algún archivo, no lo crea y te dice cuál.
2. Abre un **chat nuevo**, adjunta el zip y pega `CONTEXTO_BASE.md` seguido de este mensaje (cambia el número y los módulos de la tabla):

   > Adjunto mi proyecto en un zip. Hacemos la **ENTREGA N**: lee su sección en `ENTREGAS.md` y los documentos de `docs/referencia/` que nombre, ejecuta `python scripts/contexto.py <módulos de la tabla>` y abre completos solo los archivos que vayas a modificar.

   **Método manual** (si el chat no abre el zip): en lugar del zip, pega `CONTEXTO_BASE.md`, la salida de `python scripts/contexto.py <módulos>`, la sección de la entrega y lo que ella pida de `docs/referencia/`.
3. Copia los archivos que entregue Claude a tu proyecto y ejecuta `python scripts/verificar.py`. Si pide `reset_db.py`, ejecútalo (borra los datos de desarrollo).
4. Haz el checklist manual en el navegador. Si hay errores, pégalos en el mismo chat (últimas 20 a 30 líneas y el archivo implicado) y escribe: «Corrige solo esto; entrega únicamente el bloque cambiado».
5. Si todo está bien: pega en este archivo las notas, en `docs/TRAZABILIDAD.md` las filas que cambian, en `DECISIONES.md` las líneas nuevas, cambia el estado abajo y la «Siguiente entrega» de arriba, y haz `git add -A && git commit -m "entrega N"`. Genera un zip nuevo para la entrega siguiente.

Si el mismo error persiste tras dos intentos, abre un chat nuevo con el zip, `CONTEXTO_BASE.md` y el error. Si se agota tu cuota a mitad de una entrega, pide: «Entrega ahora una lista de lo que quedó hecho y lo que falta de esta entrega, y nada más»; guárdala, haz commit y continúa en un chat nuevo con el zip actualizado, `CONTEXTO_BASE.md`, el mismo mensaje de inicio y la frase «Ya está hecho lo que dice la lista; continúa solo con lo que falta».

## Entregas
| # | Qué logra | Requisitos | Módulos para `contexto.py` | Estado |
|---|---|---|---|---|
| 1 | Cierre de sesión que invalida el token; tiempo activo real | RF-03 | `auth desafios` | pendiente |
| 2 | Indicadores TA, NI, TR, UA con pandas; historial de indicadores; seudónimos | RF-18, 26, 27, RNF-23 | `motor_retiro progreso` + matriz | pendiente |
| 3A | Prerrequisitos y 4 conceptos nuevos con desafío | RF-09 | `desafios` + 1 desafío de ejemplo | pendiente |
| 3B | Segundos desafíos: filtrado, ordenamiento, join | RF-09 | `desafios` + 1 desafío de ejemplo | pendiente |
| 3C | Segundos desafíos: having, subconsulta, funciones de ventana | RF-09 | `desafios` + 1 desafío de ejemplo | pendiente |
| 4 | Omitir desafío; reglas R8 y R7 | RF-18, 19 | `motor_retiro desafios linea_base` + matriz | pendiente |
| 5 | Retiro acelerado R2 y estancamiento R6 | RF-19 | `motor_retiro` + matriz | pendiente |
| 6 | Recaída R3, cambio de dificultad R12, inactividad R14 | RF-19 | `motor_retiro auth` + matriz | pendiente |
| 7 | Ajuste 3.1, dificultad inicial y preferencia de retiro (R13) | RF-08, 19 | `linea_base motor_retiro` + matriz | pendiente |
| 8 | Dependencia R9, ensayo-error R10, sobreconfianza R11, oferta de ayuda | RF-14, 16, 19 | `motor_retiro asistencia desafios` + matriz | pendiente |
| 9 | Validadores V3 a V9, historial en el prompt, ayudas guardadas | RF-15–17, RNF-02, 11, 24 | `asistencia` + prompt_resumen | pendiente |
| 10 | Notificaciones con campana | RF-21 | `motor_retiro` | pendiente |
| 11 | Historial de intentos con filtros y gráficos de evolución | RF-22–24 | `progreso analitica` | pendiente |
| 12 | Docente: banco de desafíos con validación automática | RF-28, 29, RNF-08 | `desafios auth` | pendiente |
| 13A | Administrador: gestión de roles y auditoría | RF-04, RNF-08 | `auth` | pendiente |
| 13B | Reportes agregados anonimizados y exportación CSV | RF-30, RNF-23 | `analitica` + matriz (sección 10) | pendiente |
| 14 | Respaldo, manuales, checklists, consentimiento y cierre | RNF-12–15, 20, 22 | ninguno | pendiente |

**Prioridad si el tiempo o la cuota se acaban:** las entregas 1 a 9 completan el motor de reglas y la ayuda, que es el corazón de la tesis; con ellas el sistema ya supera con claridad al MVP. Las 10 y 11 completan la experiencia del estudiante, y las 12, 13A y 13B añaden los roles docente y administrador.

## Fuera del alcance por ahora
Quedan fuera a propósito porque necesitan servicios o herramientas que son pesados de construir y verificar en chats gratuitos. Están registrados como brechas en `docs/TRAZABILIDAD.md`.
- **Redis** (RF-20, RNF-03, RNF-10, RNF-16): el nivel de ayuda se guarda en la base de datos, que cumple lo esencial.
- **PostgreSQL, Docker y escalado horizontal** (RF-25, RNF-09, RNF-16): se usa SQLite; los tipos de datos son portables y bastaría cambiar `DATABASE_URL`.
- **HTTPS, despliegue y CI** (RNF-07, RNF-09): dependen de dónde se publique. Necesarios si vas a hacer el piloto con estudiantes desde un servidor.
- **Pruebas de carga y pruebas automáticas de navegador** (RNF-01, 04, 14, 20): se cubren con los checklists manuales de la entrega 14.

## Notas de lo hecho
(vacío; añade aquí de 2 a 4 líneas por entrega)
