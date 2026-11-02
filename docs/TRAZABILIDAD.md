# TRAZABILIDAD DE REQUISITOS

Estado de cada requisito de `docs/referencia/requisitos.md`. Se actualiza al terminar cada entrega. «Fuera de alcance actual» significa una brecha aceptada por ahora (ver `HOJA_DE_RUTA.md`). Las pruebas citadas son archivos de `backend/tests`.

| ID | Requisito | Estado | Entrega | Evidencia |
|---|---|---|---|---|
| RF-01 | Registro de usuarios | Cumplido | — | tests/test_auth.py |
| RF-02 | Inicio de sesión | Cumplido (el login puede devolver `mensaje_motor` de reenganche, R14; nunca falla por el motor) | 6 | tests/test_auth.py, tests/test_motor_recaida_dificultad_inactividad.py |
| RF-03 | Cierre de sesión | Cumplido (el servidor revoca el jti) | 1 | tests/test_logout.py |
| RF-04 | Gestión de roles | Parcial: el rol existe y da 403; falta gestionarlo | 13A | — |
| RF-05 | Perfil | Cumplido | — | tests/test_auth.py |
| RF-06 | Consentimiento informado | Cumplido (texto provisional) | 14 | tests/test_linea_base.py |
| RF-07 | Diagnóstico (línea base) | Cumplido | — | tests/test_linea_base.py |
| RF-08 | Nivel de ayuda inicial | Cumplido: ajuste 3.1 aplicado (no a NS0, a «Muy fácil» ni con riesgo R9) y dificultad inicial marcada en el listado; el máximo histórico inicial y la marca fija son PROVISIONALES (ver DECISIONES) | 7 | tests/test_linea_base_calculo.py, tests/test_retiro_preferencias.py |
| RF-09 | Lista de desafíos por dificultad | Cumplido: 16 desafíos, los 10 conceptos con contenido y 2 desafíos en `filtrado`, `ordenamiento`, `join`, `having`, `subconsulta` y `funciones_ventana`; contenido y prerrequisitos entre conceptos PROVISIONALES (validar con la profesora) | — | tests/test_desafios.py, tests/test_desafios_seeds.py |
| RF-10 | Enunciado y recursos | Cumplido | — | tests/test_desafios.py |
| RF-11 | Envío de consulta | Cumplido | — | tests/test_desafios.py |
| RF-12 | Ejecución en sandbox | Cumplido | — | tests/test_sandbox.py |
| RF-13 | Retroalimentación del intento | Cumplido | — | tests/test_desafios.py |
| RF-14 | Solicitud de ayuda | Cumplido; desde la entrega 8 también la oferta automática según la preferencia 3.3 (a_solicitud, ofrecer o mostrar sola) y los mínimos de AY3/AY4 con R9. PROVISIONAL: sin oferta en verificación ni de AY4, y 3.3 sin respuesta = ofrecer (ver DECISIONES) | 8 | tests/test_asistencia_api.py, tests/test_entrega8_banderas_oferta.py |
| RF-15 | Ayuda generada por IA | Parcial: validadores V1 y V2; LLM real sin probar | 9 | tests/test_asistencia_validador.py |
| RF-16 | Ayuda con contexto del estudiante | Parcial: el prompt ya lleva las banderas `dependencia` y `sobreconfianza` (entrega 8, solo como códigos); falta el historial del desafío | 9 | tests/test_prompt_builder.py, tests/test_entrega8_banderas_oferta.py |
| RF-17 | Registro de ayudas | Cumplido; cada solicitud guarda ahora `mostrada_sola`, `tipo_solicitado` e `intentos_previos` (el frontend las pierde al cerrar la pestaña) | 9 | tests/test_asistencia_api.py |
| RF-18 | Cálculo de indicadores | Cumplido: TA, NI, TR y UA con pandas; TR con tiempo activo por latidos (PROVISIONAL, hueco 45 s); UA PROVISIONAL (ver DECISIONES) | 2 | tests/test_analitica_indicadores.py, tests/test_motor_reglas.py, tests/test_latidos.py |
| RF-19 | Ajuste del nivel de ayuda (R0 a R14) | Cumplido en lo esencial: las 15 reglas existen (R0 a R14); R9, R10 y R11 desde la entrega 8 y R13 completa (3.3 y 3.4). PROVISIONAL: R9 (la ventana reemplaza a la bandera inicial con ≥ 3 desafíos; criterio de pedidos directos con el tipo solicitado), R10 (no se repite hasta 3 envíos nuevos), R11 (mensaje en todo acierto), la oferta de ayuda (ver DECISIONES), R6 (lista de refuerzo previo y mapa de prerrequisitos), R2 (TR de los 3 últimos), R12 (cuándo «pasa» a una dificultad mayor), omitir y verificación (R7) en la elección del desafío, y R13 (3.4) en el «siguiente desafío» del aviso previo, el respeto permanente de `mantener` y la reproposición | 4 a 8 | tests/test_motor_reglas.py, tests/test_omitir.py, tests/test_motor_recaida_dificultad_inactividad.py, tests/test_retiro_preferencias.py, tests/test_entrega8_banderas_oferta.py |
| RF-20 | Estado de sesión en Redis | Fuera de alcance actual: el nivel vive en la base de datos | — | niveles_soporte |
| RF-21 | Notificaciones | Parcial: avisos en pantalla al cerrar o iniciar un desafío (R3, R12, retiros pendientes de R13) y aviso de reenganche al iniciar sesión (R14); sin campana ni tabla de notificaciones | 10 | tests/test_motor_integracion.py, tests/test_retiro_preferencias.py |
| RF-22 | Progreso del estudiante | Cumplido | — | tests/test_progreso.py |
| RF-23 | Gráficos de evolución | Parcial: datos listos (`serie_historica`, tabla `indicadores_historicos`); faltan los gráficos (entrega 11) | 2, 11 | tests/test_analitica_historico.py |
| RF-24 | Filtro de historial de intentos | Pendiente | 11 | — |
| RF-25 | Almacenamiento en PostgreSQL | Fuera de alcance actual: SQLite con tipos portables | — | DECISIONES.md |
| RF-26 | Análisis con pandas | Cumplido | 2 | tests/test_analitica_indicadores.py |
| RF-27 | Exposición de indicadores | Cumplido: interfaz interna `analitica.servicio` (sin endpoint HTTP; si se requiere, llega con la entrega 11) | 2 | tests/test_analitica_historico.py |
| RF-28 | CRUD del banco de desafíos | Pendiente | 12 | — |
| RF-29 | Clasificación por dificultad y tema | Parcial: el modelo lo tiene; falta gestionarlo | 12 | — |
| RF-30 | Reportes del docente | Pendiente | 13B | — |
| RNF-01 | Tiempo de respuesta de la API | Fuera de alcance actual: sin medición | — | — |
| RNF-02 | Latencia de la ayuda con LLM | Parcial: límite de 8 s con respaldo; sin medir con el LLM real | 9 | config/llm.json |
| RNF-03 | Actualización inmediata del nivel | Parcial: se guarda en la base al cerrar el desafío | — | tests/test_motor_integracion.py |
| RNF-04 | Usuarios concurrentes | Fuera de alcance actual: sin prueba de carga | — | — |
| RNF-05 | Autenticación con JWT | Cumplido | — | tests/test_auth.py |
| RNF-06 | Contraseñas con hash seguro | Cumplido (argon2) | — | tests/test_auth.py |
| RNF-07 | Comunicaciones cifradas | Fuera de alcance actual: depende del despliegue | — | — |
| RNF-08 | Acceso por rol | Parcial: solo rutas de estudiante | 12, 13A | tests/test_recorrido_rutas.py |
| RNF-09 | Disponibilidad | Fuera de alcance actual: depende del despliegue | — | — |
| RNF-10 | Persistencia ante recarga | Parcial: el nivel está en la base; las ayudas no | 9 | niveles_soporte |
| RNF-11 | Tolerancia a fallos del LLM | Cumplido (ayuda de respaldo) | 9 | tests/test_asistencia_api.py |
| RNF-12 | Copias de seguridad | Pendiente | 14 | — |
| RNF-13 | Facilidad de aprendizaje | Pendiente: protocolo de prueba con estudiantes | 14 | — |
| RNF-14 | Diseño responsivo | Parcial: no verificado en navegador | 14 | — |
| RNF-15 | Retroalimentación visual | Parcial: revisar cada acción | 14 | — |
| RNF-16 | Escalabilidad horizontal | Fuera de alcance actual | — | — |
| RNF-17 | Documentación de la API | Cumplido (/docs) | — | — |
| RNF-18 | Arquitectura modular | Cumplido | — | backend/app/modules |
| RNF-19 | Control de versiones | Cumplido (Git) | — | — |
| RNF-20 | Compatibilidad de navegadores | Pendiente: checklist manual | 14 | — |
| RNF-21 | Proveedor de LLM intercambiable | Cumplido (mock, Groq, Anthropic) | — | tests/test_asistencia_base.py |
| RNF-22 | Consentimiento y ética | Parcial: texto provisional | 14 | tests/test_linea_base.py |
| RNF-23 | Anonimización de datos | Parcial: seudonimización HMAC lista y verificada; falta el reporte (13B) | 2, 13B | tests/test_analitica_seudonimo.py, tests/test_analitica_historico.py |
| RNF-24 | Minimización de datos al LLM | Cumplido | 9 | tests/test_prompt_builder.py |
