# VALORES Y TEXTOS PROVISIONALES

Todo lo de este documento es una propuesta que debe validarse antes de usar los resultados en la tesis. «Profesora» = la docente que asesora la tesis; «Comité» = comité de ética o de tesis. «Piloto» = datos de los primeros estudiantes, vistos en **Reportes** o con `scripts/exportar_tesis.py`. El detalle y la justificación de cada decisión están en `DECISIONES.md`. Los valores de `reglas.json` se editan sin tocar el código y requieren reiniciar el servidor.

## 1. Claves de `backend/app/config/reglas.json` marcadas `provisional: true`

| Clave | Valor | Quién valida | Cómo se calibra con el piloto |
|---|---|---|---|
| `tiempo_activo.hueco_max_seg` | 45 | Profesora | Con un hueco entre latidos mayor, la pausa no suma. Comparar `tiempo_activo_seg` con el reloj en `sesiones_desafio` (columna `tiempo_activo_origen`): si hay mucha pausa contada o muchas sesiones sin latidos, ajustar. |
| `reportes.n_minimo` | 3 | Profesora o Comité | Subirlo si, con la cantidad real de estudiantes, un grupo pequeño permite identificar a alguien (el piso efectivo es 2). |
| `r13_preferencia_ayuda.por_defecto` | `ofrecer` | Profesora | Si muchos estudiantes no responden la pregunta 3.3, revisar si `ofrecer` genera rechazos («Ahora no») en exceso. |
| `r12_cambio_dificultad.ns_minimo_tras_cambio` | 1 | Profesora | Revisar en Reportes si tras cambiar de dificultad el NS 1 evita recaídas (R3). |
| `r6_estancamiento.reglas_que_cuentan_como_refuerzo` | `["R5","R8"]` | Profesora | Añadir o quitar reglas de la lista según si R12 o R14 deben contar como «refuerzo previo». |

## 2. Umbrales de la Matriz (de diseño propio, sin marca en el archivo)
Todos se calibran con el piloto. Tras reunir datos, revisar el indicador que cada uno gobierna en **Reportes**.

| Clave | Valor | Quién valida | Cómo se calibra |
|---|---|---|---|
| `tiempo_referencia_seg` | D1 120, D2 240, D3 360 (la Matriz los llama provisionales) | Profesora | Usar la mediana del tiempo activo de quienes resuelven sin ayuda por dificultad (desempeño por concepto y dificultad). |
| `ventana.tamano` / `minimo_desafios_desde_cambio` | 5 / 3 | Profesora | Si los cambios de NS son muy lentos o muy frecuentes, ajustar. |
| `cortes_linea_base`, `valor_dominio_m` (incluye «No sé» = 0.25) | 0.70 / 0.40; tabla de m | Profesora | Contrastar con **Precisión del NS inicial**. |
| `retiro_refuerzo` (TA 0.80 / 0.50, NI 2 / 4, TR 1.25 / 1.0, 3 desafíos limpios) | ver archivo | Profesora | Contrastar con **desafíos hasta el primer retiro**, **recaídas (R3)** y la proporción de SA por bloques. |
| `recaida_y_pausas` | 2 desafíos, pausa de 3 | Profesora | Ver la tasa de recaídas tras retiro. |
| `r6_estancamiento.ns_maximo_prerrequisito_dominado` / `omisiones_muy_dificil_seguidas` | 1 / 2 | Profesora | Revisar cuántos avisos de estancamiento salen y si se repiten demasiado. |
| `r7_muy_facil`, `r14_inactividad` | 2 omisiones, 14 días | Profesora | Frecuencia de verificaciones y de mensajes de reenganche. |
| `ayuda_en_desafio`, `r9_dependencia`, `r10_ensayo_error`, `r11_sobreconfianza` | ver archivo | Profesora | Frecuencia de activación de R9 y R10 en **Reportes**; valoraciones «No útiles» de las ayudas. |

## 3. Textos provisionales
| Texto | Dónde está | Quién valida | Cómo se revisa |
|---|---|---|---|
| **Consentimiento informado, versión 1.1** (RNF-22) | `frontend/src/features/diagnostico/ConsentimientoPage.tsx`; versión en `linea_base/service.py` | **Comité** y profesora | Contrastarlo con `docs/PRUEBAS_MANUALES.md` y con lo que se guarda (ver sección 5). Si cambia el texto, subir `VERSION_CONSENTIMIENTO`. |
| Mensajes `oferta_ayuda`, `ayuda_mostrada_sola`, `cambio_dificultad`, `sugerencia_mas_basico` | `config/mensajes_fijos.json` | Profesora | Preguntar a los estudiantes del protocolo de usabilidad si los entienden. |
| Texto genérico de cambio de NS, redacción de varios conceptos en R14, aviso al bajar de tipo de ayuda y texto «CORRECCIÓN…» del reintento al LLM | `motor_retiro/mensajes.py`, `asistencia/` | Profesora | Lectura de muestras de notificaciones y ayudas. |
| Enunciados, recursos, errores típicos y ayudas de respaldo de los 16 desafíos; etiquetas D1 Básica, D2 Intermedia, D3 Avanzada | `modules/desafios/seeds.py` | Profesora | Resolverlos como estudiante; revisar los de mayor tasa de NR. |
| Aparición de `LIMIT` en el desafío de ordenamiento sin presentarlo antes | `seeds.py` | Profesora | Decidir si se mueve a otro concepto. |

## 4. Decisiones de lógica provisionales (resumen)
| Decisión | Quién valida | Cómo se calibra |
|---|---|---|
| Mapa de prerrequisitos entre conceptos (`seeds/seed.py`; lo usa R6) | Profesora | Revisar cadena; se corrige en el seed. |
| R12: «pasa» a mayor dificultad al iniciar un desafío más difícil que el más alto cerrado | Profesora | Contrastar con cuándo los estudiantes cambian de dificultad en la práctica. |
| R14: actividad = última sesión de desafío | Profesora | Piloto. |
| R2: TR sobre los 3 últimos desafíos (mediana) | Profesora | Piloto. |
| R9: la ventana reemplaza la bandera inicial con 3 o más desafíos; pedidos directos por tipo solicitado | Profesora | Frecuencia de R9. |
| R10: no se repite hasta 3 envíos nuevos; R11: mensaje en todo acierto | Profesora | Piloto. |
| Oferta de ayuda: sin oferta en verificación ni de AY4; con `mostrar_sola` solo la primera; TR en curso solo al fallar | Profesora | Valoraciones y rechazos de ofertas. |
| R13 (3.4): `aviso_previo` se aplica al siguiente desafío del mismo concepto; `mantener` se respeta siempre; si el criterio sigue cumpliéndose se vuelve a proponer | Profesora | Si molesta, añadir enfriamiento. |
| Ajuste 3.1 y máximo histórico inicial; dificultad inicial fija («Empieza aquí») | Profesora | **Precisión del NS inicial**. |
| Sin diagnóstico: NS 1 y banner «Diagnóstico pendiente» | Profesora | Contar estudiantes sin diagnóstico. |
| Definiciones de los indicadores de eficacia del retiro (sección «Reportes» de `DECISIONES.md`) | Profesora | Comparar con la Matriz, sección 7. |
| Supresión primaria de celdas pequeñas; el CSV no la aplica | Comité | Revisar riesgo de reidentificación. |
| El docente ve solución y ayudas de respaldo en el banco | Profesora | Confirmar. |
| Exactamente 3 errores típicos por desafío; AY4 debe pasar el sandbox | Profesora | Ajustar `docente/validacion.py`. |
| Administrador no cambia su propio rol; auditoría del docente no atómica | Profesora | Confirmar. |
| Tiempo activo no suma el tramo entre el último latido y el cierre (hasta ~15 s) | Profesora | Piloto. |
| Sal de seudónimos (`ANON_SALT`, 16 hex) | Comité | Definirla antes de recoger datos. |

## 5. Consentimiento (RNF-22): texto frente a lo que se registra
| Lo que se registra | ¿Lo dice el texto 1.1? |
|---|---|
| Nombre, correo y contraseña (solo su hash) | Sí (nombre y correo) |
| Respuestas del diagnóstico, preferencias, resultado | Sí |
| Cada consulta SQL enviada, su resultado, tiempos por latidos, abandonos y omisiones | Sí |
| Ayudas entregadas, valoraciones, cambios de NS, indicadores y eventos del motor | Sí (en general) |
| Envío a un proveedor externo de IA (enunciado, consulta, resultado, errores recientes, mensaje); sin nombre ni correo | Sí |
| Seudonimización, informes agregados, CSV sin código ni correos | Sí |
| Quién ve nombre y correo (solo el administrador) | Sí |
| El mensaje opcional a la IA no se guarda | No hace falta |
| **Contacto del investigador, plazo de conservación y cómo retirar los datos** (hoy no existe mecanismo) | **No: falta** |
| **Actividad de quien no acepta pero practica sin diagnóstico (se registra y entra a los CSV)** | **No: pendiente de decisión** |

Los dos últimos puntos deben resolverse con la profesora o el comité antes del piloto.
