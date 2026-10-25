# DECISIONES DEL MVP

Marcadas **PROVISIONAL** las que conviene validar con la profesora o con el piloto.

## Arquitectura y seguridad
- `POST /auth/logout` revoca el `jti` del token en `tokens_revocados` (se purgan los vencidos en cada logout) y `usuario_actual` rechaza tokens revocados con 401. Sin Redis. `SECRET_KEY` vacía genera una clave temporal (las sesiones se pierden al reiniciar). El frontend cierra la sesión local aunque falle la red.
- Token en `localStorage`. Login con mensaje único ante credenciales inválidas. Tras registrarse se inicia sesión. «Reintentar» solo comprueba `/health`.
- SQLite en desarrollo, con tipos portables para migrar a PostgreSQL por `DATABASE_URL`. Sin Alembic: `create_all` al iniciar y `scripts/reset_db.py`. Los seeds corren al iniciar.
- El registro público siempre crea `estudiante`. Docente y administrador existen en el modelo pero sin funciones aún. Docentes y administradores reciben 403 en las rutas de estudiante.
- Los valores de la Matriz y de `llm.json` se leen de `backend/app/config/*.json`. `NS_POR_DEFECTO=1`, `NS_MINIMO=0`, `NS_MAXIMO=3` son constantes del código (`motor_retiro/niveles.py`).

## Diagnóstico (línea base)
- Si el estudiante no completa el diagnóstico, la plataforma sigue usable con NS=1 y un banner «Diagnóstico pendiente»; en cada login vuelve a `/consentimiento`. **PROVISIONAL**.
- Texto del consentimiento (versión «1.0») **PROVISIONAL**: revisarlo con la profesora o el comité antes del piloto. «No acepto» no guarda nada.
- Se guardan sin aplicar: ajuste por 3.1, dificultad inicial, bandera R9 y bandera R11. Los datos crudos siempre se conservan. El motor las leerá más adelante.
- Estructurales en código: señal 1.6 = opciones c o d; señales 3.2 y 3.6 = `inmediato`; m se redondea a 6 decimales antes de comparar con los cortes. Dificultad inicial: primer nivel D1/D2 con promedio de m menor que `dominio_por_nivel_minimo`; si ninguno, D3 (regla provisional). Concepto sin ítems usa el m global; todos sus ítems en «Muy fácil» → NS1.
- El borrador del diagnóstico vive en `sessionStorage` y se descarta si cambia la versión del cuestionario.

## Desafíos y sandbox
- Sandbox con **SQLite en memoria, no el dialecto de PostgreSQL**; se informa al estudiante. Solo `SELECT/WITH`, una sentencia, autorizador de solo lectura, tiempo límite de 2 s y tope de 200 filas (desde `.env`).
- Comparación de resultados: ignora los nombres de columna y el orden de filas salvo que la solución tenga `ORDER BY` de nivel superior; decimales a 6 cifras. Por eso los enunciados fijan el orden de columnas y las soluciones con `ORDER BY` desempatan.
- **Tiempo activo** = segundos acumulados por latidos (`POST /desafios/{id}/latido`, cada 15 s con pestaña visible y actividad en los últimos 30 s); un latido cuyo hueco supera `tiempo_activo.hueco_max_seg` (45, **PROVISIONAL**, en `reglas.json`) no suma la pausa. Si la sesión no tuvo latidos, vale `fin − inicio`. `sesiones_desafio.tiempo_activo_origen` (`latidos` o `reloj`) lo registra. Si `reglas.json` no se puede leer, el latido no suma y rige `fin − inicio`. **PROVISIONAL**: al cerrar con latidos no se suma el tramo desde el último latido hasta el cierre (hasta ~15 s menos); validar con la profesora. Se guardan marcas de tiempo de cada evento para refinarlo con pandas.
- Un envío no vacío cuenta como intento aunque falle o esté bloqueado; vacío o de más de 4000 caracteres → 422 sin intento. Se puede reiniciar un desafío resuelto o abandonado (sesión nueva).
- 13 desafíos sembrados (6 del MVP + 4 de la entrega 3A + 3 de la entrega 3B, idempotentes por título; los 10 conceptos tienen al menos uno). Enunciados, recursos y ayudas **PROVISIONALES**: revisarlos con la profesora. Etiquetas de dificultad D1 Básica / D2 Intermedia / D3 Avanzada, también provisionales.
- Un fallo del motor al cerrar un desafío no rompe el cierre (CU04 EX2).
- **PROVISIONAL (mapa de prerrequisitos, entrega 3A):** `filtrado` es el concepto de entrada; `ordenamiento`, `conteo_agregacion` y `join` dependen de `filtrado`; `group_by` y `subconsulta` de `conteo_agregacion`; `having`, `join_agregacion` y `funciones_ventana` de `group_by`; `left_join` de `join`. Un solo prerrequisito por concepto (`join_agregacion` depende solo de `group_by` aunque también usa JOIN). El documento lo deja «por definir»; **debe validarlo la profesora**. Vive en `seeds/seed.py` (contenido sembrado, no umbral) y solo completa valores vacíos.
- **PROVISIONAL (contenido 3A):** los desafíos «Resumen de inscripciones pagadas del taller» (`conteo_agregacion` D1), «Funciones realizadas por sala del festival» (`group_by` D2), «Guías y sus excursiones desde noviembre» (`left_join` D2; enseña la condición de fecha en el `ON`) y «Pagos de la cooperativa de café por región en octubre» (`join_agregacion` D3), con sus errores típicos y ayudas de respaldo, requieren revisión docente.
- **PROVISIONAL (contenido 3B):** los segundos desafíos «Citas veterinarias de perros y gatos del tercer trimestre» (`filtrado` D2; enseña `IN`, `BETWEEN` inclusivo y la precedencia de `AND`/`OR`), «Podio del torneo de ajedrez del colegio» (`ordenamiento` D2; tres criterios de orden y `LIMIT`) y «Pantalla de salidas del aeropuerto con su aerolínea» (`join` D1; unión simple de dos tablas), con sus errores típicos y ayudas de respaldo, requieren revisión docente. Regla aplicada: el segundo desafío de cada concepto tiene dificultad distinta a la del primero (D1→D2, D1→D2 y D2→D1) para que R8 pueda ofrecer uno más básico. `LIMIT` aparece en el desafío de ordenamiento sin haberse presentado antes: está explicado en sus recursos; la profesora puede decidir si prefiere moverlo a otro concepto.

## Ayuda con IA
- El motor decide el tipo de ayuda; el LLM solo redacta. Al LLM nunca se envían nombre, correo, NS ni indicadores de ventana.
- `MockLLMProvider` por defecto (ayuda de respaldo rotulada como demostración). `AnthropicProvider` **no se ha probado contra la API real**, solo con un cliente simulado; si falla, cae al respaldo.
- `GroqProvider` (LLM_PROVIDER=groq, modelo `openai/gpt-oss-120b`, SDK oficial `groq`): sin streaming (el backend devuelve JSON completo). Los tokens de razonamiento de gpt-oss cuentan dentro de `max_completion_tokens`, por eso se suma `razonamiento.margen_tokens` (1500, `llm.json`) al tope de cada tipo; el largo de la respuesta lo siguen limitando las plantillas. `reasoning_effort=low`, temperatura 0.2 y tiempo límite 8 s salen de `llm.json`. Solo se usa `message.content`. Se probó con un cliente simulado; **la primera llamada real a Groq debe verificarse en la máquina del equipo**. Cualquier fallo cae al mock. La clave vive solo en `.env` (ignorado por git).
- Decisión del tipo: sube un tipo solo si hubo al menos un fallo posterior a la última ayuda; si no, repite el tipo reformulado. Si no se cumple el mínimo de fallos (AY3=2, AY4=3), baja de uno en uno. AY4 nunca es la primera ayuda. En NS0 la solicitud del estudiante da AY1. La sugerencia al bajar de tipo es un texto provisional del backend.
- Validador: solo V1 y V2, con un reintento y luego respaldo (incidente guardado). V3–V9 pendientes. El texto «CORRECCIÓN…» del reintento es provisional.
- AY4 marca el desafío NR de inmediato; si luego lo resuelve sigue NR y no cuenta como resuelto. `tiempo_relativo` = tiempo transcurrido / tiempo de referencia (definición propia). Valoraciones 👍/👎: solo se registran.
- No hay endpoint para listar las ayudas de una sesión: el frontend las guarda en `sessionStorage` y se pierden al cerrar la pestaña (la marca NR sí queda en el servidor).

## Motor de retiro (simplificado)
- Solo **R5 → R1 → R4**, en el orden de `reglas.json`. Faltan R2, R3, R6 a R14.
- Ventana: últimos 5 cierres del concepto posteriores al último cambio. TA y NI son reales; **TR usa el tiempo activo por latidos (provisional)**; UA se calcula pero R1 y R5 no la usan. Sin umbrales nuevos en `reglas.json`. Los indicadores se calculan en `modules/analitica` (entrega 2).
- Con NS=3, R5 corresponde pero se queda en 3 (R6 pendiente). R1 siempre retira en automático: no respeta aún la preferencia 3.4 (R13) ni R11/R3/R12. Las omisiones de la línea base aún no suman al contador de R7.
- El texto del aviso al estudiante sale de `mensajes_fijos.json`; `historial_niveles` guarda el motivo técnico.

## Capa analítica (entrega 2)
- Los indicadores TA, NI, TR y UA se calculan con pandas en `modules/analitica/indicadores.py` (funciones puras); la ventana (últimos 5 cierres desde el último cambio de NS) tiene una sola definición, `extractores.cierres_del_concepto`, usada por el motor y por `servicio.indicadores_ventana`. `calcular_indicadores` del motor conserva su firma y sus resultados (prueba de equivalencia con la implementación anterior).
- **PROVISIONAL (UA):** una sesión cuenta como uso de ayuda si tiene alguna solicitud y la sesión no está marcada `ayuda_mostrada_sola`. Aún no hay origen por solicitud: si el estudiante pidió ayuda además de recibir una mostrada sola, no se cuenta. Se afina en la entrega 8.
- **PROVISIONAL (sal de seudónimos):** `id_pseudonimo` = HMAC-SHA256 del `usuario_id` con `ANON_SALT`, 16 caracteres hexadecimales. Sin `ANON_SALT` se usa una sal temporal con aviso en el log y los seudónimos cambian al reiniciar; definirla antes del piloto.
- `indicadores_historicos` guarda una fila por cierre con los indicadores que usó el motor (ventana incluyendo el cierre) y el NS resultante. Si el motor falla no se escribe fila; si falla el guardado, el cierre y el ajuste de NS no se afectan.
- `agregados` toma el estado más reciente de cada estudiante-concepto de `indicadores_historicos`; no recalcula desde las sesiones. Solo devuelve seudónimos.
- Dependencia nueva: `pandas>=2.2.3,<4` (verificado con 2.2.3 y 3.0).

## Progreso (entrega 10)
- `GET /progreso/resumen` (solo estudiante): desafíos distintos resueltos (sin contar los NR), abandonos, NS actual por concepto (1 si no hay registro), ayudas por tipo y los 10 últimos cambios de `historial_niveles`, con el texto de `mensajes_fijos.json`.
- Sin actividad (sin sesiones, ayudas ni cambios) → valores iniciales y una sugerencia de resolver un desafío. Error de base → 503 con mensaje amable; la página ofrece «Reintentar».

## Limitaciones conocidas
- Verificado en Linux con Python 3.12 y Node 22; **no probado en Git Bash/Windows ni en un navegador real**. Sin pruebas automáticas del frontend.
- El `node_modules` del zip no sirve en otro sistema operativo: ejecutar `npm install` en cada máquina.
