# ENTREGAS

Cada entrega es un chat. Adjunta el zip del proyecto (`python scripts/empaquetar.py` lo crea), pega `CONTEXTO_BASE.md` y escribe el mensaje de inicio de `HOJA_DE_RUTA.md` con el número de la entrega. Claude lee de este archivo la sección que le toca, ejecuta `python scripts/contexto.py` con los módulos que indica la línea «Revisa en el proyecto» y abre completos solo los archivos que va a modificar. Si tu chat no puede abrir zips, pega tú la sección y la salida de `contexto.py` (método manual de `HOJA_DE_RUTA.md`). Los casos de uso (`casos_de_uso_resumen.md`) son opcionales: la tarea se entiende sin ellos.

Orden: primero lo que hace funcionar el motor y la ayuda (entregas 1 a 9), después lo que completa la experiencia (10 y 11), los roles docente y administrador (12 y 13) y el cierre (14).

---

## ENTREGA 1: Cierre de sesión seguro y tiempo activo real

**Revisa en el proyecto:** `python scripts/contexto.py auth desafios` · **Cubre:** RF-03, y mejora TR (indicador de tiempo relativo).

**Tarea**
1. **Invalidar el token al cerrar sesión.** El JWT lleva `jti`. Tabla `tokens_revocados` (jti único, expira_en). `POST /auth/logout` registra el jti y borra los ya vencidos. `usuario_actual` rechaza tokens revocados con 401 y un mensaje claro. En el frontend, «Cerrar sesión» llama al servidor y, aunque falle la red, borra el token local y vuelve al login.
2. **Tiempo activo real.** Hoy `tiempo_activo_seg` es `fin − inicio` e incluye pausas, lo que puede impedir el retiro (R1). Añade `POST /desafios/{id}/latido` [estudiante]: suma al tiempo activo de la sesión en curso los segundos desde el latido anterior, solo si el hueco es menor o igual a `tiempo_activo.hueco_max_seg` (clave nueva en `reglas.json`, `provisional: true`, valor 45). Columnas nuevas nullable en `sesiones_desafio`: `ultimo_latido_en` y `tiempo_activo_origen` (`latidos` o `reloj`). Al cerrar: si hubo latidos, se usa lo acumulado; si no, `fin − inicio` como hoy.
3. **Frontend:** un hook que envía un latido cada 15 s solo si la pestaña está visible y hubo actividad (teclado, ratón o foco) en los últimos 30 s. Un fallo del latido se ignora en silencio (no muestra errores).

**Pruebas:** token usado tras el logout → 401; token válido sigue funcionando; latidos con un hueco largo no suman la pausa; sin latidos se usa `fin − inicio`; el motor sigue leyendo `tiempo_activo_seg`.

**Hecho cuando:** cierro sesión, copio el token viejo y la API lo rechaza; dejo un desafío abierto 5 minutos sin tocar nada y su tiempo activo no incluye esa pausa.

---

## ENTREGA 2: Capa analítica con pandas

**Revisa en el proyecto:** `python scripts/contexto.py motor_retiro progreso` + `docs/referencia/matriz_resumen.md` · **Cubre:** RF-18, RF-23 (datos), RF-26, RF-27, RNF-23.

**Tarea**
1. Añade `pandas` (versión con wheels para Python 3.13). Módulo nuevo `modules/analitica/` con: `extractores.py` (consultas a DataFrames de sesiones, intentos, ayudas e historial), `indicadores.py` (**TA, NI, TR y UA** exactamente como los define la Matriz, sección 1; UA cuenta pedir o aceptar ayuda y no cuenta la ayuda mostrada sola), `seudonimizar.py` (`id_pseudonimo` = HMAC-SHA256 del `usuario_id` con `ANON_SALT` del `.env`, truncado; ningún DataFrame analítico lleva nombre ni correo) y `servicio.py` como **interfaz pública** de los indicadores: `indicadores_ventana(db, usuario_id, concepto_id)`, `serie_historica(db, usuario_id, concepto_id=None)` y `agregados(db, ...)` (este último lo usará el reporte de la entrega 13).
2. Reemplaza `motor_retiro/indicadores.calcular_indicadores` por una llamada a la capa analítica **manteniendo la firma y los resultados** de R1, R4 y R5.
3. Tabla nueva `indicadores_historicos` (usuario_id, concepto_id, sesion_id, ta, ni, tr, ua, n_ventana, ns, creado_en): una fila por cierre de desafío, escrita desde el hook del motor dentro de un `try/except` para no romper el cierre.
4. `.env.example`: `ANON_SALT` comentada.

**Pruebas:** una prueba de equivalencia con los casos actuales de R1/R4/R5; indicadores con DataFrames sintéticos (UA incluida); seudónimo estable y distinto por usuario; ninguna salida analítica contiene nombre ni correo.

**Hecho cuando:** tras cerrar un desafío aparece una fila en `indicadores_historicos` y el nivel de ayuda se sigue ajustando como antes.

---

## ENTREGA 3A: Contenido, prerrequisitos y 4 conceptos nuevos

**Revisa en el proyecto:** `python scripts/contexto.py desafios` + **un** desafío completo de `modules/desafios/seeds.py` como modelo de calidad + la sección 9 de `matriz_resumen.md` · **Cubre:** RF-09 (contenido).

**Tarea**
1. **Prerrequisitos:** completa `conceptos.prerrequisito_id` con una cadena razonable de los 10 conceptos (`filtrado`, `ordenamiento`, `conteo_agregacion`, `join`, `group_by`, `having`, `left_join`, `subconsulta`, `join_agregacion`, `funciones_ventana`). El documento deja el mapa «por definir»: márcalo PROVISIONAL en DECISIONES.md y dime que lo valide mi profesora.
2. **4 desafíos nuevos**, uno por cada concepto sin desafío: `conteo_agregacion` (D1), `group_by` (D2), `left_join` (D2), `join_agregacion` (D3).

**Reglas de contenido (iguales a las del MVP):** dominio distinto al del cuestionario (tienda) y variado; no repetir los 11 ítems del cuestionario; `sandbox_setup_sql` con datos suficientes para distinguir una consulta correcta de una casi correcta; el enunciado fija el orden de las columnas; las soluciones con `ORDER BY` desempatan; 3 errores típicos con una consulta de ejemplo que debe fallar; `ayudas_respaldo` AY1 a AY4 (AY1 sin código; AY2 con un ejemplo de **otro dominio**; AY3 con al menos 2 `___`; AY4 = la solución explicada); `tiempo_referencia_seg` desde `reglas.json`. Seeds idempotentes por título.

**Pruebas:** las pruebas de seeds existentes (la solución pasa por el sandbox, el error típico falla, AY1 sin código, AY3 con ≥ 2 `___`) cubren los nuevos desafíos; los 10 conceptos tienen al menos un desafío.

**Hecho cuando:** `/desafios` muestra los 10 conceptos en el filtro y puedo resolver los 4 nuevos. Al final, lista los textos que debe revisar mi profesora (todos son PROVISIONALES).

---

## ENTREGA 3B: Contenido, segundos desafíos (parte 1)

**Revisa en el proyecto:** `python scripts/contexto.py desafios` + un desafío completo de `seeds.py` · **Cubre:** RF-09 (contenido), base para R8.

**Tarea:** 3 desafíos nuevos: un segundo desafío para `filtrado`, `ordenamiento` y `join`. Intenta que su dificultad sea **distinta** a la del primero (si el existente es D1, el nuevo es D2; si es D2 o D3, el nuevo es de una dificultad menor), para que R8 pueda ofrecer «un desafío más básico del mismo concepto» cuando sea posible. Mismas reglas de contenido que la entrega 3A. Si no cabe, entrega 2 y espera `continúa`.

**Pruebas y hecho cuando:** igual que 3A; cada uno de esos 3 conceptos tiene ahora 2 desafíos.

---

## ENTREGA 3C: Contenido, segundos desafíos (parte 2)

**Revisa en el proyecto:** `python scripts/contexto.py desafios` + un desafío completo de `seeds.py` · **Cubre:** RF-09 (contenido).

**Tarea:** 3 desafíos nuevos: un segundo desafío para `having`, `subconsulta` y `funciones_ventana`, con las mismas reglas que la 3B. Al terminar habrá 16 desafíos y los 10 conceptos con contenido.

**Pruebas y hecho cuando:** igual que 3A; el total de desafíos sembrados es 16.

---

## ENTREGA 4: Omitir un desafío, R8 y R7

**Revisa en el proyecto:** `python scripts/contexto.py motor_retiro desafios linea_base` + `docs/referencia/matriz_resumen.md` · **Cubre:** RF-18, RF-19.

**Tarea (según la Matriz, secciones 5 a 7)**
1. **Omitir.** `POST /desafios/{id}/omitir` {motivo: `muy_facil` | `muy_dificil`}: guarda en `omisiones` con `origen=desafio`, cierra la sesión como omitida (no cuenta como resuelto ni como fallo y **no entra en la ventana**) y dispara el motor. Si hace falta un estado nuevo de sesión, dímelo (`reset_db.py`). Frontend: botón «Omitir» con un diálogo para elegir el motivo.
2. **R8** («Muy difícil»): el NS sube 1 (máximo 3) y la respuesta incluye `sugerido`: un desafío más básico del mismo concepto, o `null` si no hay. Si omite 2 seguidas y el NS ya era 3, se deja registrado para R6 (entrega 5).
3. **R7** («Muy fácil»): contador por concepto que suma las omisiones de la línea base y de los desafíos. Al llegar a 2 se asigna un **desafío de verificación**: no se ofrece ayuda automática (la ayuda sigue disponible si el estudiante la pide, pero entonces ya no cuenta como SA); si lo resuelve como SA cuenta como el primero de los 3 desafíos limpios de R2. El contador se reinicia al asignar la verificación. Si un concepto tuvo 2 o más ítems en la línea base y todos se omitieron por «Muy fácil», la verificación se asigna al terminar el diagnóstico.
4. `ContextoRegla` y `evaluador` se amplían respetando el orden de `reglas.json` (R6, R8, R7, R5, R2, R1, R4: la primera que corresponde detiene las siguientes; R6 y R2 llegan en la entrega 5). `ResultadoRegla` gana una `accion` (cambiar NS, verificación, sugerir) y la clave del mensaje en `mensajes_fijos.json`.
5. **Un único punto para los mensajes del motor al estudiante** (`motor_retiro/mensajes.py`), para que la entrega 10 los convierta en notificaciones sin tocar las reglas.
6. Frontend: muestra los mensajes de refuerzo, verificación y el desafío sugerido.

**Pruebas:** tabla de casos de R8 y R7; las omisiones no entran en la ventana; la verificación asignada al registrarse; un fallo del motor no rompe el cierre.

**Hecho cuando:** omito un desafío por «Muy difícil», mi nivel de ayuda en ese concepto sube y me sugiere uno más básico; omito dos por «Muy fácil» y se me asigna la verificación.

---

## ENTREGA 5: Retiro acelerado (R2) y estancamiento (R6)

**Revisa en el proyecto:** `python scripts/contexto.py motor_retiro` + `docs/referencia/matriz_resumen.md` · **Cubre:** RF-19.

**Tarea**
1. **R2 Retiro acelerado:** los últimos 3 desafíos desde el último cambio fueron SA, con 1 intento cada uno y TR ≤ 1.0 → el NS baja 2 (mínimo 0). Solo con NS ≥ 1 y con desafíos posteriores al último cambio; un desafío con ayuda mostrada sola no es SA. Ya hay una clave `desafios_limpios_acelerado` en `reglas.json`.
2. **R6 Estancamiento:** con NS = 3, (a) TA < 0.50, al menos 3 desafíos desde el último cambio y un refuerzo previo en el concepto (se consulta en `historial_niveles`), o (b) 2 omisiones «Muy difícil» seguidas con el NS ya en 3. Acción: si el prerrequisito está dominado (su NS vigente ≤ 1) o no tiene, mensaje `estancamiento_derivar`; si no, mensaje `estancamiento_previo_sin_dominar` con el nombre del concepto previo y un enlace a sus desafíos (`/desafios?concepto=...`).
3. El evaluador queda completo en el orden **R6, R8, R7, R5, R2, R1, R4**.
4. Frontend: muestra el aviso de retiro acelerado y el de estancamiento con su enlace.

**Pruebas:** tabla de casos para R2 y R6 (incluye NS 3 con TA baja con y sin refuerzo previo, prerrequisito dominado y sin dominar); prioridad entre reglas; integración: el NS cambia y la primera ayuda del siguiente desafío del concepto corresponde al nuevo NS.

**Hecho cuando:** tras 3 desafíos limpios seguidos mi NS baja 2 niveles; con NS 3 y mal desempeño sostenido me sugiere practicar el concepto previo.

---

## ENTREGA 6: Recaída (R3), cambio de dificultad (R12) e inactividad (R14)

**Revisa en el proyecto:** `python scripts/contexto.py motor_retiro auth` + `docs/referencia/matriz_resumen.md` · **Cubre:** RF-19.

**Tarea**
1. **R3 Recaída:** tras un retiro, los 2 desafíos siguientes son CE o NR → el NS vuelve al valor anterior y se pausan los retiros 3 desafíos. Para esto guarda en `niveles_soporte` el NS previo al último retiro y un contador de pausa (columnas nullable; dime si requiere `reset_db.py`).
2. **R12 Cambio de dificultad:** el NS del concepto pasa a ser el mayor entre su NS actual y 1, y R1 y R2 se pausan 3 desafíos. La Matriz no define cuándo «pasa» el estudiante a una dificultad mayor: usa una definición operativa **PROVISIONAL** (iniciar un desafío de una dificultad mayor a la más alta ya cerrada en ese concepto) y anótala en DECISIONES.md.
3. **R14 Inactividad:** 14 días o más sin actividad (usa la última sesión de desafío del estudiante) → el NS de cada concepto sube 1 **sin superar `ns_maximo_historico`** y se muestra el mensaje de reenganche. Se evalúa al iniciar sesión (sin tareas programadas) dentro de un `try/except`; el login devuelve un campo opcional `mensaje_motor` y el frontend lo muestra como aviso.
4. Todo pasa por `motor_retiro/mensajes.py` y se registra en `eventos_motor` e `historial_niveles`.

**Pruebas:** tabla de casos de R3, R12 y R14; la pausa de 3 desafíos bloquea R1 y R2 y después se levanta; el login no falla si el motor falla.

**Hecho cuando:** simulo una recaída y mi NS vuelve al valor anterior con el mensaje de recaída; un estudiante con 14 días de inactividad recibe el reenganche al entrar.

---

## ENTREGA 7: Lo que faltaba de R0 y preferencias de retiro (R13, pregunta 3.4)

**Revisa en el proyecto:** `python scripts/contexto.py linea_base motor_retiro` + `docs/referencia/matriz_resumen.md` · **Cubre:** RF-08, RF-19.

**Tarea**
1. **Ajuste por la pregunta 3.1** (R0). El módulo de cálculo ya tiene `ajustar_por_3_1` y guarda el resultado sin aplicarlo. Aplícalo al NS inicial con las condiciones de la Matriz: el resultado queda entre NS1 y NS2, no se aplica a NS0, ni al NS1 de la excepción «Muy fácil», **ni si la bandera inicial de dependencia (R9) marca riesgo**. Guarda también el NS previo al ajuste. Solo afecta a registros nuevos.
2. **Dificultad inicial.** El listado de desafíos marca con «Empieza aquí» el nivel (D1, D2 o D3) que corresponde al estudiante, sin bloquear los demás.
3. **R13, pregunta 3.4 (cómo retirar la ayuda).** Los retiros de R1 y R2 respetan la preferencia: `automatico` (como hoy); `aviso_previo` (se avisa y se aplica en el siguiente desafío salvo que pulse «Mantener la ayuda»); `preguntar` (se aplica solo si acepta); `mantener` (no se retira ni se avisa; el motor registra que se cumplió el criterio). Tabla `ajustes_pendientes` y `POST /ajustes/{id}/responder` {aceptar | mantener}. Usa los mensajes `retiro_aviso_previo`, `retiro_preguntar` y `retiro_mantener_nivel` de `mensajes_fijos.json`. Frontend: botón «Mantener la ayuda» y diálogo de pregunta.

**Pruebas:** tabla del ajuste por 3.1 (cada opción y cada excepción); dificultad inicial; un retiro bajo cada valor de 3.4; aceptar y mantener actualizan o no el NS.

**Hecho cuando:** un estudiante nuevo que eligió «una pista general» en 3.1 empieza con un NS menor; con la preferencia «preguntar» el retiro espera mi respuesta.

---

## ENTREGA 8: Dependencia (R9), ensayo y error (R10), sobreconfianza (R11) y oferta de ayuda

**Revisa en el proyecto:** `python scripts/contexto.py motor_retiro asistencia desafios` + `docs/referencia/matriz_resumen.md` · **Cubre:** RF-14, RF-16, RF-19.

**Tarea**
1. **R9:** bandera inicial (línea base) y dinámica con la UA de la capa analítica (≥ 80 % de desafíos con ayuda, o ≥ 50 % de pedidos AY3 o AY4 con un intento o menos previo; se reevalúa con al menos 3 desafíos). Efecto: **+1 al mínimo de fallos de AY3 y AY4** (clave `incremento_minimos_por_dependencia`; ajusta `decision.py`) y la bandera `dependencia` hacia el prompt.
2. **R11:** con la bandera inicial de sobreconfianza, R1 exige además los 2 últimos desafíos en SA; tras un acierto se muestra el mensaje `sobreconfianza_acierto`; el prompt recibe la bandera `sobreconfianza`.
3. **R10 (dentro del desafío):** 3 envíos fallidos seguidos con menos de 30 s entre ellos → la respuesta del intento incluye `reflexion` con el mensaje `ensayo_error`. No bloquea la ayuda. Se registra en `eventos_motor`.
4. **Oferta de ayuda:** con 2 o más fallos, o TR del desafío en curso ≥ 1.5, y NS ≥ 1, la respuesta del intento incluye `oferta_ayuda` (según la preferencia 3.3: `a_solicitud` no ofrece; `ofrecer` muestra una tarjeta «¿Quieres una pista?»; `mostrar_sola` pide la ayuda automáticamente y la marca `ayuda_mostrada_sola`, que no cuenta para UA ni para R9). En NS 0 solo existe el botón.
5. Las banderas llegan al prompt **solo como los códigos de la plantilla**, nunca como números ni indicadores. Registra en `eventos_motor` cada activación de R9, R10 y R11.

**Pruebas:** tabla por bandera; el mínimo de AY3 y AY4 sube con R9; el prompt generado con banderas no contiene NS ni indicadores ni datos personales; la oferta respeta cada valor de 3.3.

**Hecho cuando:** fallo 3 veces rápido y veo la pregunta de reflexión; con 2 fallos me aparece la oferta de ayuda (según mi preferencia).

---

## ENTREGA 9: Ayuda completa (validadores V3 a V9, historial y ayudas guardadas)

**Revisa en el proyecto:** `python scripts/contexto.py asistencia` + `docs/referencia/prompt_resumen.md` · **Cubre:** RF-15, RF-16, RF-17, RNF-02, RNF-11, RNF-24.

**Tarea**
1. **V3 a V9** añadidos a `VALIDACIONES` con la estructura existente (una función por validador, su prueba y su motivo de reintento), tal como los define `prompt_resumen.md`. V4 analiza la sintaxis del SQL del ejemplo sin ejecutarlo; V6 ejecuta la consulta de AY4 en el sandbox y compara. **V9 (más de 8 s) no reintenta: entrega la ayuda de respaldo directamente.**
2. **Historial relevante en el prompt (RF-16):** resumen de lo ocurrido en el desafío (errores previos del estudiante y ayudas ya entregadas), sin datos personales, dentro de los datos permitidos.
3. **Ayudas guardadas en el servidor:** `GET /desafios/{id}/ayudas` (sesión actual o la última). El frontend deja de depender de `sessionStorage`, así que las ayudas no se pierden al cerrar la pestaña.
4. **Opcional, si tengo clave de LLM:** `scripts/probar_llm.py` ejecuta una pequeña batería de solicitudes (unas 3 por tipo de ayuda) y reporta latencia, cuántas pasan los validadores y cuántas caen al respaldo, para calibrar `llm.json`. Yo lo ejecuto con mi clave nueva.

**Pruebas:** un caso por validador (pasa y falla); V9 va directo al respaldo; prueba con valores «canario» (nombre, correo, NS, indicadores) que **no aparecen** en lo que recibe el proveedor con todas las funciones activas.

**Hecho cuando:** recargo la página en medio de un desafío y las ayudas recibidas siguen ahí.

---

## ENTREGA 10: Notificaciones

**Revisa en el proyecto:** `python scripts/contexto.py motor_retiro` · **Cubre:** RF-21.

**Tarea**
1. Tabla `notificaciones` (usuario_id, tipo, texto, regla, concepto_id nullable, leida, creada_en, ajuste_id nullable). Se crean desde `motor_retiro/mensajes.py`: retiro, refuerzo, recaída, reenganche, verificación y estancamiento. Sin duplicados por evento. Los textos salen de `mensajes_fijos.json`.
2. Endpoints propios del estudiante: `GET /notificaciones`, `POST /notificaciones/{id}/leida`, `POST /notificaciones/leer-todas`.
3. Frontend: campana con contador en el encabezado (se actualiza al cerrar un desafío y cada 60 s con la pestaña visible), un panel desplegable y la página `/notificaciones`. Las que requieren decisión (R13) son accionables. Cada pantalla con sus 4 estados. Sin correo ni push.

**Pruebas:** una notificación por evento sin duplicados; solo las ve su dueño; marcar como leída.

**Hecho cuando:** cuando mi nivel de ayuda cambia, la campana muestra una notificación que puedo marcar como leída.

---

## ENTREGA 11: Progreso avanzado (historial y gráficos)

**Revisa en el proyecto:** `python scripts/contexto.py progreso analitica` · **Cubre:** RF-22, RF-23, RF-24.

**Tarea**
1. `GET /progreso/intentos?desafio_id&desde&hasta&pagina&tam`: historial de intentos propio con filtros por desafío y rango de fechas (fechas inválidas → 422 con mensaje amable), paginado.
2. `GET /progreso/evolucion?concepto&desde&hasta`: series de TA, NI, TR y UA (de `indicadores_historicos`) y la línea de tiempo del NS (de `historial_niveles`).
3. Frontend en `/progreso`: gráficos de evolución con **recharts** (versión fija) y una tabla de intentos con selector de desafío y rango de fechas. Cada gráfico acompañado de su tabla o texto alternativo. Estados vacío y error con «Reintentar».

**Pruebas:** filtros combinados, paginación, solo datos propios, rango vacío.

**Hecho cuando:** filtro mis intentos por desafío y fechas, y veo cómo evolucionaron mis indicadores y mi NS.

---

## ENTREGA 12: Rol docente, banco de desafíos

**Revisa en el proyecto:** `python scripts/contexto.py desafios auth` · **Cubre:** RF-28, RF-29, RNF-08.

**Tarea**
1. Rutas `/docente/desafios` con `requiere_rol('docente', 'administrador')`; el menú y las rutas del frontend solo para esos roles. El estudiante recibe 403 con un mensaje claro.
2. **CRUD** de desafíos con clasificación por **dificultad (D1 a D3)** y por **tema o concepto**, y todos los campos del modelo. **Validación automática al guardar** con el sandbox: el setup corre, la solución se acepta a sí misma, los 3 errores típicos fallan, AY1 sin código, AY3 con al menos 2 `___`, AY2 sin usar las tablas del desafío. Los problemas se listan campo por campo y no se guarda un desafío inválido. Vista previa tal como la ve el estudiante.
3. **Integridad:** un desafío con sesiones **no se borra**: se desactiva (`activo=false`). El borrado físico solo si no tiene sesiones. Cambiar la solución o el setup de uno ya usado pide confirmación.
4. Para probar necesito un docente: crea un seed opcional `DOCENTE_EMAIL` y `DOCENTE_PASSWORD` en `.env` (vacíos = no se crea).

**Pruebas:** permisos por rol; la validación rechaza cada tipo de defecto; desactivar oculta el desafío al estudiante sin perder su historial; el estudiante no puede entrar a `/docente`.

**Hecho cuando:** entro como docente, creo un desafío que se valida solo, y aparece en la lista del estudiante.

---

## ENTREGA 13A: Administración de roles

**Revisa en el proyecto:** `python scripts/contexto.py auth` · **Cubre:** RF-04, RNF-08.

**Tarea**
1. `GET /admin/usuarios` (paginado, con búsqueda), `PUT /admin/usuarios/{id}/rol` y activar o desactivar, solo para el administrador. No se puede quitar el último administrador ni el propio rol. El primer administrador se crea con `ADMIN_EMAIL` y `ADMIN_PASSWORD` del `.env` (vacíos = no se crea).
2. Tabla `auditoria` (usuario_id, accion, objeto, detalle, creado_en) con los cambios de rol y las acciones del docente sobre el banco (hazlo con una función simple que se pueda llamar desde la entrega 12).
3. Frontend: página «Usuarios» solo para el administrador.

**Pruebas:** matriz de permisos (estudiante y docente reciben 403); reglas del último administrador; la auditoría registra el cambio de rol. Ampliar `test_recorrido_rutas.py` para que recorra las rutas de admin sin 5xx.

**Hecho cuando:** como administrador convierto a un usuario en docente y su menú cambia.

---

## ENTREGA 13B: Reportes agregados

**Revisa en el proyecto:** `python scripts/contexto.py analitica` + `docs/referencia/matriz_resumen.md` (sección 10) · **Cubre:** RF-30, RNF-23.

**Tarea**
1. Reportes para docente y administrador con filtro de fechas, **siempre agregados y con seudónimos** (nunca nombres ni correos), usando `analitica.agregados`: uso (estudiantes activos por semana, sesiones, intentos); desempeño por concepto y dificultad (tasas SA, CP, CE y NR, intentos medios, TR); distribución de NS por concepto; ayudas por tipo y valoraciones; retiros y refuerzos; m medio de la línea base; y los **indicadores de eficacia del retiro** de la Matriz: proporción de conceptos que llegan a NS0 sin recaída, desafíos hasta el primer retiro, proporción de SA a lo largo de las sesiones, frecuencia de activación de R9 y R10 y precisión del NS inicial.
2. **Supresión de celdas pequeñas:** no se muestra un grupo con menos de `reportes.n_minimo` estudiantes (clave nueva en `reglas.json`, `provisional: true`, valor 3).
3. **Exportación:** `GET /reportes/exportar` (CSV seudonimizado de intentos, ayudas, cambios de NS e indicadores) y `scripts/exportar_tesis.py` con lo mismo desde la terminal.
4. Frontend: página «Reportes» con tablas y gráficos simples, solo para docente y administrador.

**Pruebas:** permisos por rol; ninguna salida (JSON ni CSV) contiene nombre ni correo; la supresión de celdas pequeñas funciona.

**Hecho cuando:** descargo un CSV para el análisis de mi tesis y no aparece ningún dato personal.

---

## ENTREGA 14: Cierre

**Revisa en el proyecto:** `HOJA_DE_RUTA.md`, `docs/TRAZABILIDAD.md` y `DECISIONES.md` · **Cubre:** RNF-12, RNF-13, RNF-14, RNF-15, RNF-20, RNF-22.

**Tarea**
1. `scripts/respaldo.py` y `scripts/restaurar.py` (copia segura de la base SQLite con `sqlite3.backup` y restauración), con una prueba de ida y vuelta.
2. **Textos de documentación:** `docs/manual_estudiante.md`, `manual_docente.md` y `manual_administrador.md` (una página cada uno); `docs/PROVISIONALES.md` con todos los valores y textos provisionales (clave, valor, quién lo valida, cómo se calibra con el piloto); README y DECISIONES.md consolidados y **verificados contra el proyecto real** (variables, comandos, puertos).
3. **Checklists manuales** (documentos, sin código): `docs/PRUEBAS_MANUALES.md` con pasos para comprobar el diseño responsivo en 3 anchos, el funcionamiento en Chrome, Edge, Firefox y Safari y que cada acción da una respuesta visible (RNF-14, RNF-15, RNF-20); y `docs/PRUEBA_USABILIDAD.md` con un protocolo de usabilidad para unos 5 estudiantes (tareas, tasa de finalización sin ayuda, tiempo, escala SUS) (RNF-13).
4. **Consentimiento (RNF-22):** revisa el texto contra lo que realmente se registra y márcalo para que lo valide mi profesora o el comité.
5. Actualiza `docs/TRAZABILIDAD.md` con el estado final.

**Checklist final (reporta cada punto):**
- [ ] `python scripts/verificar.py` pasa; `git clone` más los pasos del README funcionan desde cero en Git Bash.
- [ ] Recorrido completo del estudiante: registro, consentimiento, diagnóstico, desafíos de los 10 conceptos, ayuda, cambios de nivel con notificación, progreso con gráficos.
- [ ] Docente crea y valida un desafío; administrador gestiona roles; los reportes no muestran datos personales.
- [ ] Sin clave de LLM todo funciona en modo demostración; con la clave nueva la ayuda sale del LLM real.
- [ ] No hay secretos en el repositorio ni en su historial.
