# Matriz de reglas de retiro de asistencia (resumen para implementar)
Fuente: «Matriz de reglas y criterios de retiro de asistencia» (docx). Se omiten las citas a artículos y las columnas «respaldo»; el resto es fiel. Los umbrales viven en `backend/app/config/reglas.json`. Todos los números son de diseño propio, a calibrar con el piloto. **El motor decide; el LLM solo redacta.**

## 1. Conceptos
- **Desafío:** pertenece a un concepto y a una dificultad D1/D2/D3 (Nivel 1/2/3 del cuestionario = D1/D2/D3). **NS 0–3 por concepto** (0 autónomo, 3 alto). Retirar = bajar NS; reforzar = subirlo. **AY1** pista general, **AY2** ejemplo guiado, **AY3** solución parcial, **AY4** solución completa.
- **Ventana:** últimos 5 desafíos del concepto **desde el último cambio de NS**. Las **omisiones (R7/R8) no entran** en la ventana (ni TA, NI, TR, UA, ni «desafíos desde el último cambio»).
- **m:** valor de dominio 0–1 de la línea base (acierto + confianza), se calcula **una sola vez**; después manda el NS.
- **Resultado de un desafío:** **SA** sin ayuda (ni pedida, ni aceptada, ni mostrada sola) · **CP** con ayuda prevista (≤ la que le correspondía por NS; en NS 0 la ayuda pedida AY1 cuenta como prevista) · **CE** con ayuda extra · **NR** abandonado o vio AY4 (NR en cuanto se entrega AY4, aunque luego resuelva). Éxito = SA o CP.
- **Indicadores de la ventana:** **TA** = éxitos ÷ desafíos · **NI** = mediana de envíos hasta resolver (en NR, los envíos hechos) · **TR** = mediana de (tiempo activo real ÷ tiempo de referencia de su dificultad) · **UA** = proporción de desafíos donde pidió o aceptó ayuda (la ayuda mostrada sola sin pedirla ni aceptarla **no** cuenta).

## 2. Reglas que nunca se rompen
- El estudiante siempre puede pedir ayuda (el retiro quita la **oferta automática**, no el acceso).
- **AY4 nunca es la primera ayuda**; solo se llega escalando.

## 3. NS (Tabla 6)
| NS | Qué hace | Línea base (antes de ajustes) | También se llega por |
|---|---|---|---|
| 0 | No ofrece ayuda por iniciativa; si la piden: AY1 | m ≥ 0.70 | retiro (R1/R2) |
| 1 | Primera ayuda AY1; puede ofrecerla tras fallos | 0.40 ≤ m < 0.70 | refuerzo desde 0 (R5, R8, R12, R14); retiro desde 2 (R1) o 3 (R2); reversión R3 |
| 2 | Primera ayuda AY2 | m < 0.40 | refuerzo desde 1 (R5, R8, R14); retiro desde 3 (R1); R3 |
| 3 | Primera ayuda AY3 | nunca por línea base | refuerzo desde 2 (R5, R8, R14); R3 |

## 4. Parámetros (Tabla 7; claves en reglas.json)
Ventana 5 / mínimo 3 desafíos desde el último cambio · tiempo de referencia D1 2 min, D2 4, D3 6 (provisional) · cortes m 0.70/0.40; dificultad inicial: promedio de m por nivel ≥ 0.70 = dominado · TA retiro ≥ 0.80 / refuerzo < 0.50 · NI retiro ≤ 2 / refuerzo ≥ 4 · TR retiro estándar ≤ 1.25 / acelerado ≤ 1.0 · 3 desafíos limpios (SA, 1 intento) para R2/R7 · recaída: 2 desafíos CE/NR; pausa de 3 desafíos sin retiro tras recaída o cambio de dificultad · prerrequisito dominado: NS ≤ 1 · omisión «Muy fácil»: 2 (suma línea base + desafíos) · omisión «Muy difícil» seguidas con NS 3: 2 · oferta de ayuda: 2 fallos / TR 1.5 · mínimo AY3 = 2 fallos, AY4 = 3 (+1 con dependencia R9) · R10: 3 envíos fallidos seguidos con < 30 s entre ellos · dependencia: ≥ 80 % de desafíos con ayuda, o ≥ 50 % de pedidos AY3/AY4 con ≤ 1 intento previo · sobreconfianza: ≥ 2 errores con confianza 4–5 (no cuentan «No sé» ni omisiones) · inactividad 14 días.

## 5. Matriz (Tabla 9)
**R0 NS inicial (al terminar la línea base, por concepto).** m ≥ 0.70 → NS0; 0.40–0.69 → NS1; < 0.40 → NS2. Concepto sin ítems → m global (promedio de m de la Parte 2). **Excepción:** todos los ítems del concepto omitidos por «Muy fácil» → NS1 (no 0) y esas omisiones se suman al contador de R7; al llegar a 2 se da el **desafío de verificación** (si el concepto tuvo ≥ 2 ítems: al registrarse; si tuvo 1: con la siguiente omisión «Muy fácil» en un desafío). Si hay ítems respondidos, las omisiones entran al cálculo de m (Tabla 15).
 **Ajuste por 3.1** (tras aplicar los cortes; resultado siempre entre NS1 y NS2): «pista general» baja 1 (NS2→1; NS1 se queda); «ejemplo guiado» no cambia; «solución parcial» o «completa» suben 1 (NS1→2; NS2 se queda). **No se aplica** a NS0, ni al NS1 de la excepción «Muy fácil», ni si hay riesgo de dependencia (R9). Elegir «solución completa» no cambia que AY4 nunca es primera ayuda.
 **Dificultad inicial:** empieza en el primer nivel cuyo promedio de m es < 0.70: D1 si no domina el Nivel 1; D2 si domina 1 pero no 2; D3 si domina ambos. Las omisiones entran con su valor de Tabla 15; vale para todos los conceptos. Regla provisional; el paso a mayor dificultad durante la práctica está pendiente.

**Bloque 2: retirar**
- **R1 Retiro estándar:** NS ≥ 1, ≥ 3 desafíos desde el último cambio y en la ventana TA ≥ 0.80 **y** NI ≤ 2 **y** TR ≤ 1.25 → NS baja 1.
- **R2 Retiro acelerado:** los últimos 3 desafíos desde el último cambio fueron SA, 1 intento cada uno y TR ≤ 1.0 → NS baja 2 (mínimo 0). Solo NS ≥ 1 y desafíos posteriores al último cambio. Un desafío con ayuda mostrada sola **no** es SA.
- **R3 Recaída:** tras un retiro, los 2 desafíos siguientes son CE o NR → el NS vuelve al valor anterior y no hay retiros durante 3 desafíos.

**Bloque 3: mantener / reforzar**
- **R4 Mantener:** ninguna otra aplica (p. ej. TA 0.50–0.80 con NI < 4, o TA ≥ 0.80 con tiempo alto o muchos intentos). Ir despacio con buena TA = deliberación, no problema.
- **R5 Refuerzo:** ≥ 3 desafíos desde el último cambio y (TA < 0.50, o NI ≥ 4 con TA < 0.80) → NS sube 1 (máx. 3).
- **R6 Estancamiento:** NS = 3 y (a) TA < 0.50, ≥ 3 desafíos desde el último cambio y ya hubo un refuerzo previo en el concepto; o (b) 2 omisiones «Muy difícil» seguidas con el NS ya en 3 al llegar la segunda. *(En el código, «refuerzo previo» = filas de `historial_niveles` con regla R5 o R8, lista editable en `reglas.json`; PROVISIONAL, ver DECISIONES.)* → Si el prerrequisito está dominado (su NS vigente ≤ 1) o no tiene: sugerir docente/material externo. Si no (NS 2 o 3): sugerir practicar el concepto previo y ofrecer sus desafíos.

**Bloque 4: omitir un desafío**
- **R7 Omisión «Muy fácil»:** acumula 2 de un mismo concepto (línea base + desafíos) → no retira por sí solo; se da un **desafío de verificación sin ayuda**; si lo resuelve SA cuenta como el primero de los 3 limpios de R2. El contador se reinicia al asignar la verificación. No entra en la ventana.
- **R8 Omisión «Muy difícil»:** no cuenta como fallo ni entra en la ventana; **NS sube 1 (máx. 3)** y se ofrece un desafío más básico del mismo concepto. Si omite 2 seguidas y el NS ya era 3 → derivación de R6 (b).

**Bloque 5: protecciones**
- **R9 Dependencia:** en la ventana, ayuda pedida/aceptada en ≥ 80 % de los desafíos o ≥ 50 % de los pedidos son AY3/AY4 con ≤ 1 intento previo. También **bandera inicial** si la línea base cumple ≥ 2 de 3: 1.6 = «obtener la consulta resuelta» o «ambas formas»; 3.2 = «inmediato»; 3.6 = «la veo de inmediato». Se reevalúa con la ventana cuando hay ≥ 3 desafíos. Efecto: **+1 al mínimo de fallos de AY3 y AY4**; las pistas usan preguntas que hacen pensar; el retiro sigue su curso.
- **R10 Ensayo y error:** ≥ 3 envíos fallidos seguidos con < 30 s entre ellos → antes de más ayuda se pregunta «¿Qué devolvió tu consulta y qué esperabas?». Actúa **dentro del desafío**; no forma parte de la secuencia de cierre.
- **R11 Sobreconfianza:** la línea base marca ≥ 2 errores con confianza 4–5 → para retirar por R1 se exigen además **los 2 últimos desafíos en SA**; tras un acierto se muestra el mensaje fijo de explicar/simplificar; al LLM se envía la bandera `sobreconfianza`.

**Bloque 6: contexto**
- **R12 Cambio de dificultad:** el estudiante pasa a desafíos de dificultad superior (p. ej. D1→D2) → el NS en ese concepto pasa a ser max(NS actual, 1); **R1 y R2 se pausan 3 desafíos**.
- **R13 Preferencias:** **3.3** (recibir ayuda): NS 0 solo a solicitud; NS ≥ 1 la ayuda se muestra sola, se ofrece o se da a petición, sin superar lo que eligió. **3.4** (retirar): automático · con aviso previo y opción de rechazar · preguntando · mantener siempre el nivel (sin retiro automático; el motor registra que se cumplió el criterio).
- **R14 Inactividad:** ≥ 14 días sin actividad → el NS de cada concepto sube 1 **sin superar el máximo histórico** y se muestra el mensaje de reenganche.

## 6. Orden de evaluación al cerrar un desafío
**R6 → R8 → R7 → R5 → R2 → R1 → R4.** La primera que corresponde detiene las siguientes. R0 (al registrarse) y R14 (al volver) son aparte. R3, R9, R10, R11, R12, R13 **no están en la secuencia**: condicionan o modifican las otras.

## 7. Dentro del desafío (Tabla 11)
- 0–1 fallo y TR < 1.5: no interviene.
- ≥ 2 fallos o TR ≥ 1.5: **ofrece** la ayuda del NS vigente (respetando mínimos de AY3/AY4; si no se cumplen, el tipo inmediatamente inferior) si NS ≥ 1 y la preferencia 3.3 lo permite. En NS 0 solo el botón. Con 3.3 = «mostrar sola», se muestra sin pedirla (no cuenta para UA ni R9).
- Pide ayuda: recibe la del NS vigente; AY3/AY4 solo con el mínimo de fallos (2 / 3); si no, el tipo inferior y la sugerencia de reintentar.
- Pide más: sube un tipo por solicitud **solo si hubo ≥ 1 fallo nuevo**; si no, repite el tipo reformulado. Al entregar AY4 → NR inmediato; si pide más tras AY4 solo se recuerda que ya es NR.
- R10 activa: pregunta de reflexión antes de más ayuda.

## 8. Qué puede mostrar cada ayuda (Tabla 12)
AY1: orientación sin código ni cláusula exacta · AY2: caso parecido paso a paso con **otras tablas y otro dominio** · AY3: consulta con ___ en las partes clave (≥ 2) · AY4: consulta completa y explicación. Validar: AY1/AY2 no contienen la solución; AY4 se ejecuta y coincide; AY2 con sintaxis válida; AY3 con los huecos y fragmentos coherentes con la solución.

## 9. Decisiones que el documento deja abiertas (Tabla 14) → marcar PROVISIONAL
**Mapa de prerrequisitos entre conceptos (PROVISIONAL, definido en `seeds/seed.py`; lo usa R6)** · tiempos de referencia · cuándo pasa el estudiante a una dificultad mayor durante la práctica (R12 solo regula el NS) · si la preferencia 3.4 «mantener» se respeta siempre o solo al inicio · confianza por desafío (no incluida) · aclarar en la pregunta 3.1 que la solución completa nunca es primera ayuda (cambia el cuestionario oficial: decide tu docente) · validar con el piloto el ajuste por 3.1, R9 inicial, «No sé» = 0.250 y el corte NS ≤ 1 de R6.

## 10. Indicadores para saber si el retiro funciona (sección 7; sin metas numéricas)
Proporción de conceptos que llegan a NS0 sin recaída (R3) · nº de desafíos hasta el primer retiro · proporción de SA a lo largo de las sesiones · frecuencia de activación de R9 y R10 · precisión del NS inicial (¿coincide con el desempeño en los primeros desafíos?).

## 11. Valor de dominio m (Tabla 15)
Confianza 5/4/3/2/1 → acierta 0.975/0.875/0.725/0.600/0.500 · se equivoca 0.025/0.125/0.275/0.400/0.500 · «No sé» = 0.250 (error, cualquier confianza) · omisión «Muy fácil» = 0.975 · «Muy difícil» = 0.025. Conceptos: P1,P4 filtrado; P2 ordenamiento; P3 conteo/agregación; P5 JOIN; P6 GROUP BY; P7 HAVING; P8 LEFT JOIN; P9 subconsulta; P10 JOIN+agregación; P11 funciones de ventana. (Ya implementado en el MVP.) Usos de otras preguntas: 1.1–1.4 contexto; 1.5 se compara con m (no cambia nada); 1.6, 3.2, 3.6 → R9; 3.1 → R0; 3.3, 3.4 → R13; 3.5 → tono.
