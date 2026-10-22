# Prompt base y lógica de ajuste dinámico (resumen para implementar)
Fuente: «Prompt base y lógica de ajuste dinámico» (docx). Los textos del prompt, tonos, banderas y mensajes fijos **ya están en** `backend/app/config/plantillas_llm.json` y `mensajes_fijos.json`; aquí solo lo que falta por implementar.

## Reparto de funciones
Motor de reglas: NS, tipo de ayuda, cuándo ofrecer, retiro, banderas. LLM: solo redacta el tipo pedido con el tono y las banderas. Validador: comprueba antes de mostrar. El cierre del desafío no usa el LLM.

## Datos que recibe el LLM (ya implementado; conservar)
Siempre: tipo_ayuda, tono, concepto, dificultad, enunciado, esquema_sql, errores_tipicos, estado (intento, fallos, tiempo_relativo del desafío en curso, ayudas previas), + si existen: codigo_estudiante (≤ 4000), resultado_obtenido, mensaje_estudiante (≤ 500), banderas si aplican. **solucion_referencia solo en AY3 y AY4.** Nunca NS, TA/NI/TR/UA de la ventana, nombre ni correo.

## Banderas hacia el LLM (solo estos dos códigos)
`dependencia` (cierra con una pregunta que haga explicar qué intentó; en AY1 esa pregunta reemplaza a la del tipo) y `sobreconfianza` (abre con una frase que invite a comprobar con el resultado esperado). Las reglas del tipo mandan sobre tono y banderas.

## Validadores (V1–V9) · procedimiento: si falla uno, **un reintento** añadiendo el motivo; si vuelve a fallar → ayuda de respaldo + incidente registrado. El estudiante nunca recibe un error técnico.
| # | Verificación | Cómo | Si falla |
|---|---|---|---|
| V1 | JSON válido con tipo_entregado, mensaje, codigo_sql | parsear | reintento |
| V2 | tipo_entregado = tipo pedido | comparar | reintento |
| V3 | AY1 sin código ni solución | sin bloque de código; la solución normalizada no aparece en el texto | reintento |
| V4 | AY2 no resuelve el desafío ni usa sus tablas | el código no usa tablas/columnas del desafío (comparar nombres) y es SQL válido (análisis sintáctico); la corrección conceptual se evalúa con rúbrica (no ejecutable) | reintento |
| V5 | AY3 con ≥ 2 «___» y sin la solución completa | contar «___»; comparar con la solución normalizada; las partes no en blanco coinciden, en orden, con fragmentos de la solución | reintento |
| V6 | AY4 correcta | ejecutarla (solo lectura, tiempo límite) y comparar su resultado con el de la solución | reintento |
| V7 | longitud e idioma | dentro del máximo de palabras del tipo (llm.json) y en español | reintento |
| V8 | sin reglas internas ni datos personales | buscar «NS», «nivel de soporte», «retiro», correos, enlaces | reintento |
| V9 | tiempo ≤ 8 s | medir latencia | **respaldo directo, sin reintento** |

## Otras salvaguardas
Texto del estudiante delimitado por etiquetas y no tratado como instrucciones · SQL solo en sandbox de solo lectura · cada ayuda con la etiqueta «Generada por IA, puede contener errores» y 👍/👎 (solo se registra) · si el LLM no responde, ayuda de respaldo y el avance no se bloquea.

## Parámetros de llamada (ya en llm.json)
Temperatura 0.2 · max_tokens AY1 150 / AY2 450 / AY3 350 / AY4 500 · 8 s · 1 reintento · salida JSON · prompting directo (sin RAG ni fine-tuning). El máximo de AY4 es ajustado: si se corta falla V1; ampliarlo si hace falta tras probar con el LLM real.
