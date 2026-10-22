# TRAZABILIDAD DE REQUISITOS

Estado de cada requisito de `docs/referencia/requisitos.md`. Se actualiza al terminar cada entrega. «Fuera de alcance actual» significa una brecha aceptada por ahora (ver `HOJA_DE_RUTA.md`). Las pruebas citadas son archivos de `backend/tests`.

| ID | Requisito | Estado | Entrega | Evidencia |
|---|---|---|---|---|
| RF-01 | Registro de usuarios | Cumplido | — | tests/test_auth.py |
| RF-02 | Inicio de sesión | Cumplido | — | tests/test_auth.py |
| RF-03 | Cierre de sesión | Parcial: el servidor no invalida el token | 1 | — |
| RF-04 | Gestión de roles | Parcial: el rol existe y da 403; falta gestionarlo | 13A | — |
| RF-05 | Perfil | Cumplido | — | tests/test_auth.py |
| RF-06 | Consentimiento informado | Cumplido (texto provisional) | 14 | tests/test_linea_base.py |
| RF-07 | Diagnóstico (línea base) | Cumplido | — | tests/test_linea_base.py |
| RF-08 | Nivel de ayuda inicial | Parcial: falta aplicar el ajuste 3.1 y la dificultad inicial | 7 | tests/test_linea_base_calculo.py |
| RF-09 | Lista de desafíos por dificultad | Parcial: 6 desafíos en 6 de 10 conceptos | 3A, 3B, 3C | tests/test_desafios.py |
| RF-10 | Enunciado y recursos | Cumplido | — | tests/test_desafios.py |
| RF-11 | Envío de consulta | Cumplido | — | tests/test_desafios.py |
| RF-12 | Ejecución en sandbox | Cumplido | — | tests/test_sandbox.py |
| RF-13 | Retroalimentación del intento | Cumplido | — | tests/test_desafios.py |
| RF-14 | Solicitud de ayuda | Cumplido | — | tests/test_asistencia_api.py |
| RF-15 | Ayuda generada por IA | Parcial: validadores V1 y V2; LLM real sin probar | 9 | tests/test_asistencia_validador.py |
| RF-16 | Ayuda con contexto del estudiante | Parcial: sin historial del desafío en el prompt | 9 | tests/test_prompt_builder.py |
| RF-17 | Registro de ayudas | Cumplido (el frontend las pierde al cerrar la pestaña) | 9 | tests/test_asistencia_api.py |
| RF-18 | Cálculo de indicadores | Parcial: TA y NI reales; TR provisional; sin UA | 1, 2 | tests/test_motor_reglas.py |
| RF-19 | Ajuste del nivel de ayuda (R0 a R14) | Parcial: 3 de 15 reglas (R1, R4, R5) y R0 parcial | 4 a 8 | tests/test_motor_reglas.py |
| RF-20 | Estado de sesión en Redis | Fuera de alcance actual: el nivel vive en la base de datos | — | niveles_soporte |
| RF-21 | Notificaciones | Parcial: solo aviso en pantalla al cerrar un desafío | 10 | tests/test_motor_integracion.py |
| RF-22 | Progreso del estudiante | Cumplido | — | tests/test_progreso.py |
| RF-23 | Gráficos de evolución | Pendiente | 2, 11 | — |
| RF-24 | Filtro de historial de intentos | Pendiente | 11 | — |
| RF-25 | Almacenamiento en PostgreSQL | Fuera de alcance actual: SQLite con tipos portables | — | DECISIONES.md |
| RF-26 | Análisis con pandas | Pendiente | 2 | — |
| RF-27 | Exposición de indicadores | Parcial: función interna del motor | 2 | — |
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
| RNF-23 | Anonimización de datos | Pendiente | 2, 13B | — |
| RNF-24 | Minimización de datos al LLM | Cumplido | 9 | tests/test_prompt_builder.py |
