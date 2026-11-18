# PROTOCOLO DE PRUEBA DE USABILIDAD (RNF-13)

**Objetivo:** comprobar que estudiantes de SQL sin entrenamiento previo en la plataforma pueden completar las tareas básicas sin ayuda del evaluador, y medir su percepción de usabilidad con la escala SUS.
**Participantes:** unos 5 estudiantes del perfil objetivo (el grupo de validación de la tesis, antes del piloto). Con 5 personas se detectan la mayoría de los problemas graves de la interfaz; no es una muestra para generalizar.
**Duración:** unos 45 minutos por persona, de forma individual. **Material:** laptop con Chrome, servidor en marcha con base limpia (`reset_db.py`) y la IA en modo demostración o real (la misma para todos), hoja de observación (sección 5), cronómetro, y registro de pantalla solo si la persona lo autoriza.

## 1. Antes de empezar
- Una cuenta nueva por participante: ellos hacen el registro (es la Tarea 1). Usa el texto del consentimiento versión 1.1 **ya validado**; no pruebes con estudiantes sin esa validación.
- Explica que se prueba la plataforma, no a la persona; que puede parar cuando quiera; y que piense en voz alta.
- **No ayudes.** Si queda atascada más de 3 minutos en una tarea, anota «no completada», da la mínima pista necesaria y pasa a la siguiente.

## 2. Tareas
Lee cada tarea en voz alta, sin nombrar botones ni pantallas.

| N.º | Tarea (lo que se le dice) | Éxito = |
|---|---|---|
| T1 | «Crea tu cuenta y entra a la plataforma.» | Llega al consentimiento o al diagnóstico |
| T2 | «Lee cómo se usarán tus datos y decide.» | Acepta (o rechaza) sabiendo qué hace |
| T3 | «Completa el diagnóstico inicial.» | Termina las 3 partes y ve su resultado |
| T4 | «Elige un desafío y resuélvelo.» | Envía una consulta y ve el resultado |
| T5 | «Te cuesta: consigue una ayuda.» | Obtiene una ayuda con «Pedir ayuda» |
| T6 | «Dinos si la ayuda te sirvió.» | Usa «Útil» o «No útil» |
| T7 | «Decide que este desafío no es para ti y pasa a otro.» | Usa Abandonar u Omitir |
| T8 | «Revisa cómo vas.» | Abre Progreso y dice cuántos resolvió |
| T9 | «Cambia tu contraseña y sal de la plataforma.» | Lo logra desde Perfil y cierra sesión |

## 3. Medidas por tarea
- **Finalización sin ayuda (sí / sí con pista / no):** meta, al menos 80 % de las tareas completadas sin ayuda; ninguna tarea en la que fallen 2 o más de 5 personas.
- **Tiempo:** segundos desde que se lee la tarea hasta el éxito (o hasta rendirse). Se reporta la mediana por tarea; sirve para comparar tareas, no como meta.
- **Errores y dudas:** clics en lugares equivocados, mensajes que no entendieron, ayudas del evaluador.
- **Dificultad percibida:** después de cada tarea, «¿Qué tan fácil fue?» de 1 (muy difícil) a 7 (muy fácil).

## 4. Cuestionario SUS (al final)
Pide responder cada afirmación de 1 (totalmente en desacuerdo) a 5 (totalmente de acuerdo):
1. Creo que me gustaría usar esta plataforma con frecuencia.
2. Encontré la plataforma innecesariamente compleja.
3. Pensé que la plataforma era fácil de usar.
4. Creo que necesitaría el apoyo de una persona técnica para poder usarla.
5. Encontré que las diversas funciones de la plataforma estaban bien integradas.
6. Pensé que había demasiada inconsistencia en la plataforma.
7. Imagino que la mayoría de las personas aprendería a usar esta plataforma muy rápidamente.
8. Encontré la plataforma muy incómoda de usar.
9. Me sentí muy seguro/a usando la plataforma.
10. Necesité aprender muchas cosas antes de poder empezar con la plataforma.

**Puntaje:** en los ítems impares resta 1 a la respuesta; en los pares calcula 5 menos la respuesta; suma los diez valores y multiplica por 2,5 (resultado de 0 a 100). Se promedian las personas. Referencia habitual: 68 es el promedio de la escala; por debajo de 68 hay margen de mejora, y desde unos 80 la usabilidad se considera muy buena. Además pregunta: «¿Qué fue lo más confuso?», «¿Qué cambiarías?» y «¿Entendiste cuándo y por qué te ofrecía ayuda o cambiaba tu nivel?».

## 5. Hoja de observación (una por persona)
| Participante | Tarea | Sin ayuda (sí / pista / no) | Tiempo (s) | Facilidad (1-7) | Errores y comentarios |
|---|---|---|---|---|---|
| P1 | T1 | | | | |

Tras las sesiones reúne todo en una tabla: finalización por tarea, mediana de tiempo, facilidad media y SUS por persona y promedio.

## 6. Qué hacer con los resultados
1. Ordena los problemas por gravedad: **bloquea** la tarea, **retrasa** o **molesta**; y por cuántas personas lo sufrieron.
2. Corrige primero lo que bloqueó a 2 o más personas; anota en `DECISIONES.md` lo que se cambie.
3. Si hubo cambios importantes, repite con 2 o 3 personas nuevas.
4. Reporta en la tesis la tasa de finalización, los tiempos, el SUS (con n = 5 solo como indicio) y las limitaciones (pocos participantes y un solo entorno).
5. Los datos de la prueba (cuentas, intentos) no se mezclan con los del piloto: usa una base aparte o resetéala antes de empezar el piloto, y guarda las notas sin nombres.
