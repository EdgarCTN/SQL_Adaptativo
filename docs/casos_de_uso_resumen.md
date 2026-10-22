# Casos de uso CU01–CU08 (resumen para pegar en el chat)

Fuente: Casos_de_Uso v1.3. Se omiten diagramas y prototipos. Pega SOLO la sección del CU de la entrega.


---
## CU01 - Gestionar cuenta y acceso a la plataforma

**Descripción.** Esta funcionalidad permite gestionar el acceso a la plataforma. Un nuevo estudiante puede registrar su cuenta; posteriormente, un usuario registrado puede iniciar sesión mediante correo y contraseña. El sistema genera un token JWT, identifica el rol asignado y restringe las funciones según dicho rol. El estudiante también puede consultar y actualizar los datos básicos de su perfil y cualquier usuario autenticado puede cerrar su sesión.
**Actores.** 
-   Estudiante: usuario principal que puede registrarse, iniciar y cerrar sesión, y consultar o actualizar los datos básicos de su perfil.
-   Administrador / Docente: usuario registrado que inicia y cierra sesión y accede únicamente a las funciones habilitadas para su rol.
**Precondiciones.** La plataforma debe encontrarse disponible. Para iniciar sesión, el usuario debe contar con una cuenta registrada; para consultar o editar el perfil debe encontrarse autenticado.
**Pos Condiciones.** Al finalizar correctamente, la cuenta del nuevo estudiante queda registrada cuando corresponda, el usuario autenticado dispone de una sesión válida con su rol identificado, los cambios de perfil quedan almacenados y, al cerrar sesión, el token vigente queda invalidado.
**Flujo Básico.** 
1. El usuario accede a la plataforma.
2. El sistema presenta las opciones de inicio de sesión y, para un nuevo estudiante, registro de usuario.
3. Si es un nuevo estudiante, selecciona la opción de registro e ingresa nombre, correo institucional y contraseña. [EX1]
4. El sistema valida los datos y registra la cuenta del estudiante.
5. El usuario registrado ingresa su correo y contraseña para iniciar sesión. [EX2]
6. El sistema valida las credenciales y genera un token de acceso JWT.
7. El sistema identifica el rol asignado al usuario (Estudiante o Administrador/Docente).
8. El sistema habilita o restringe las funcionalidades disponibles de acuerdo con el rol identificado. [EX3]
9. El estudiante autenticado puede consultar los datos básicos de su perfil.
10. Si lo requiere, el estudiante actualiza sus datos básicos y confirma los cambios. [EX4]
11. El sistema valida y guarda la actualización del perfil.
12. Cuando el usuario selecciona cerrar sesión, el sistema invalida el token de acceso vigente y el caso de uso termina.
**Excepciones.** 
[EX1]: Datos de registro incompletos o no válidos
El sistema informa al estudiante que debe completar o corregir los datos requeridos y retorna al formulario de registro.
[EX2]: Credenciales de acceso no válidas
El sistema informa que el correo o la contraseña no son válidos y permite un nuevo intento de inicio de sesión.
[EX3]: Acceso no autorizado por rol
El sistema impide el acceso a la función solicitada cuando no corresponde al rol asignado y mantiene al usuario dentro de las opciones autorizadas.
[EX4]: Datos de perfil no válidos
El sistema informa qué datos deben corregirse y no guarda los cambios hasta que la información sea válida.
**Requerimientos no funcionales.** Aplican: RNF-01, RNF-05, RNF-06, RNF-07, RNF-08, RNF-13, RNF-20

---
## CU02 - Resolver un desafío

**Descripción.** Esta funcionalidad permite al estudiante resolver un desafío dentro de la plataforma. El sistema lista los desafíos disponibles clasificados por nivel de dificultad, presenta el desafío seleccionado, recibe la respuesta del estudiante, la valida automáticamente y registra cada intento junto con el resultado obtenido, el tiempo empleado y el número de intento.
**Actores.** Estudiante: usuario principal que consulta los desafíos disponibles, selecciona un desafío y envía una respuesta o solución.
**Precondiciones.** El estudiante debe haber iniciado sesión en la plataforma. Deben existir desafíos disponibles en el banco para ser presentados al estudiante.
**Pos Condiciones.** Al finalizar el caso de uso, la respuesta enviada queda validada como correcta o incorrecta y el intento queda registrado con el resultado obtenido, el tiempo empleado y el número de intento.
**Flujo Básico.** 
1. El estudiante accede a la opción de desafíos disponibles.
2. El sistema lista los desafíos disponibles clasificados por nivel de dificultad. [EX1]
3. El estudiante selecciona el desafío que desea resolver.
4. El sistema presenta el enunciado y los recursos asociados al desafío seleccionado. [EX2]
5. El estudiante desarrolla una respuesta o solución al desafío.
6. El estudiante envía su respuesta al sistema. [EX3]
7. El sistema valida automáticamente la respuesta enviada y determina si es correcta o incorrecta.
8. El sistema registra el intento, incluyendo el resultado obtenido, el tiempo empleado y el número de intento.
9. El sistema comunica al estudiante el resultado de la validación y el caso de uso termina.
**Excepciones.** 
[EX1]: No existen desafíos disponibles
El sistema informa al estudiante que no existen desafíos disponibles para mostrar y el caso de uso termina.
[EX2]: No es posible presentar el desafío seleccionado
El sistema informa que el desafío no se encuentra disponible y retorna al listado de desafíos.
[EX3]: Respuesta no válida para envío
El sistema solicita al estudiante corregir o completar la respuesta antes de continuar con la validación.
**Requerimientos no funcionales.** Aplican: RNF-01, RNF-04, RNF-13, RNF-14, RNF-15, RNF-20

---
## CU03 - Solicitar ayuda adaptativa (pista dinámica)

**Descripción.** Esta funcionalidad permite al estudiante solicitar una pista mientras resuelve un desafío. El sistema construye un prompt utilizando el enunciado del desafío, el nivel de ayuda vigente y el historial relevante necesario; posteriormente solicita al LLM una pista adaptada y registra la solicitud de ayuda realizada.
**Actores.** 
Estudiante: usuario que solicita una pista durante la resolución de un desafío.
Servicio LLM: servicio de modelo de lenguaje utilizado por la plataforma para generar la pista adaptada.
**Precondiciones.** El estudiante debe haber iniciado sesión y encontrarse resolviendo un desafío. Debe existir un nivel de asistencia vigente para el estudiante y la integración con el servicio LLM debe estar configurada.
**Pos Condiciones.** Al finalizar el caso de uso, el estudiante recibe una pista acorde con su nivel de ayuda vigente y la solicitud queda registrada con el nivel de ayuda entregado y el momento en que se realizó.
**Flujo Básico.** 
1. El estudiante se encuentra resolviendo un desafío.
2. El estudiante selecciona la opción para solicitar ayuda o una pista dinámica.
3. El sistema obtiene el enunciado del desafío, el nivel de ayuda vigente y el historial relevante necesario para contextualizar la solicitud.
4. El sistema construye el prompt que será enviado al LLM, evitando incluir datos personales identificables del estudiante.
5. El sistema envía la solicitud al servicio LLM. [EX1]
6. El LLM genera una pista acorde con el nivel de ayuda vigente del estudiante.
7. El sistema presenta al estudiante la pista generada. [EX2]
8. El sistema registra la solicitud de ayuda, incluyendo el nivel de ayuda entregado y el momento de la solicitud.
9. El caso de uso termina y el estudiante continúa con la resolución del desafío.
**Excepciones.** 
[EX1]: Servicio LLM no disponible o error en la generación
El sistema informa al estudiante de forma controlada que la ayuda no puede generarse en ese momento, sin afectar las demás funciones de la plataforma.
[EX2]: Respuesta del LLM vacía o no utilizable
El sistema informa que no fue posible obtener una pista válida y permite al estudiante realizar una nueva solicitud de ayuda.
**Requerimientos no funcionales.** Aplican: RNF-02, RNF-07, RNF-11, RNF-15, RNF-21, RNF-24

---
## CU04 - Ajustar el nivel de asistencia según desempeño

**Descripción.** Esta funcionalidad permite a la plataforma ajustar de forma dinámica el nivel de asistencia disponible para el estudiante. El sistema evalúa el desempeño del estudiante a partir de la tasa de aciertos, el tiempo de resolución y el número de intentos, aplica la matriz de reglas y criterios de retiro de asistencia para determinar el siguiente nivel de ayuda, actualiza el estado de sesión en Redis y notifica al estudiante cuando su nivel de asistencia cambia.
**Actores.** Estudiante: usuario cuyo desempeño es evaluado y que recibe la notificación cuando su nivel de asistencia disponible cambia. El proceso de evaluación y ajuste es ejecutado de forma automática por el sistema.
**Precondiciones.** El estudiante debe haber iniciado sesión y haber enviado una respuesta a un desafío cuyo intento ya fue registrado (CU02). Debe existir un nivel de asistencia vigente para el estudiante, asignado a partir de su nivel inicial estimado, y la matriz de reglas y criterios de retiro de asistencia debe encontrarse configurada.
**Pos Condiciones.** Al finalizar el caso de uso, el estado de sesión del estudiante en Redis queda actualizado con el nivel de asistencia vigente, los umbrales de desempeño y la temporización asociada. Si el nivel de asistencia cambió, el estudiante queda notificado del nuevo nivel disponible; en caso contrario, se mantiene el nivel anterior.
**Flujo Básico.** 
1. El estudiante envía la respuesta a un desafío y el sistema registra el intento (CU02).
2. El sistema obtiene los indicadores de desempeño del estudiante: tasa de aciertos, tiempo de resolución y número de intentos. [EX1]
3. El sistema evalúa el desempeño del estudiante en función de dichos indicadores.
4. El sistema recupera la matriz de reglas y criterios de retiro de asistencia. [EX2]
5. El sistema aplica la matriz de reglas y determina el siguiente nivel de ayuda que corresponde al estudiante.
6. El sistema actualiza en Redis el estado de sesión del estudiante, incluyendo el nivel de asistencia vigente, los umbrales de desempeño y la temporización asociada. [EX3]
7. El sistema compara el nivel determinado con el nivel de asistencia anterior. Si el nivel no cambió, el caso de uso termina.
8. Si el nivel cambió, el sistema notifica al estudiante el nuevo nivel de asistencia disponible y el caso de uso termina.
**Excepciones.** 
[EX1]: Indicadores de desempeño insuficientes o no disponibles
El sistema no modifica el nivel de asistencia vigente, conserva el estado de sesión actual y el caso de uso termina sin afectar la resolución del desafío.
[EX2]: Matriz de reglas no disponible o no válida
El sistema mantiene el nivel de asistencia vigente, registra el error para su revisión y permite al estudiante continuar con la resolución del desafío.
[EX3]: Error al actualizar el estado de sesión
El sistema conserva el último nivel de asistencia confirmado, informa al estudiante de forma controlada y reintenta la actualización sin afectar las demás funciones de la plataforma.
**Requerimientos no funcionales.** Aplican: RNF-03, RNF-10, RNF-15, RNF-18

---
## CU05 - Consultar seguimiento y progreso

**Descripción.** Esta funcionalidad permite al estudiante consultar su avance dentro de la plataforma. El sistema muestra un panel con los desafíos resueltos, el nivel de asistencia actual y las ayudas utilizadas; presenta de forma gráfica la evolución histórica de los indicadores de desempeño y permite filtrar el historial de intentos por desafío y por rango de fechas.
**Actores.** Estudiante: usuario que consulta su panel de progreso, la evolución de sus indicadores de desempeño y su historial de intentos.
**Precondiciones.** El estudiante debe haber iniciado sesión en la plataforma. Para visualizar información en el panel y en los indicadores históricos, deben existir intentos o solicitudes de ayuda registrados por el estudiante.
**Pos Condiciones.** Al finalizar el caso de uso, el estudiante ha visualizado su panel de progreso, la evolución histórica de sus indicadores de desempeño y, si lo requirió, el historial de intentos filtrado. Esta consulta no modifica la información registrada.
**Flujo Básico.** 
1. El estudiante accede a la opción de seguimiento y progreso.
2. El sistema obtiene la información de progreso del estudiante. [EX1] [EX2]
3. El sistema muestra el panel de progreso con los desafíos resueltos, el nivel de asistencia actual y las ayudas utilizadas.
4. El estudiante selecciona la opción para ver la evolución de sus indicadores de desempeño.
5. El sistema muestra de forma gráfica la evolución histórica de los indicadores de desempeño del estudiante.
6. El estudiante accede al historial de intentos y, si lo requiere, aplica filtros por desafío y por rango de fechas. [EX3]
7. El sistema muestra el historial de intentos correspondiente a los filtros aplicados.
8. El estudiante finaliza la consulta y el caso de uso termina.
**Excepciones.** 
[EX1]: El estudiante no registra actividad
El sistema informa que aún no existe actividad registrada, muestra el panel con valores iniciales y sugiere resolver un desafío para comenzar el seguimiento.
[EX2]: No es posible obtener la información de progreso
El sistema informa de forma controlada que la información no puede mostrarse en ese momento y permite al estudiante reintentar la consulta.
[EX3]: Filtros no válidos o sin resultados
Si el rango de fechas no es válido, el sistema solicita corregirlo antes de aplicar el filtro. Si no existen intentos que cumplan los filtros, el sistema informa que no se encontraron resultados y permite modificar los criterios de búsqueda.
**Requerimientos no funcionales.** Aplican: RNF-01, RNF-04, RNF-13, RNF-14, RNF-15, RNF-20

---
## CU06 - Completar diagnóstico inicial (línea base)

**Descripción.** Esta funcionalidad permite al estudiante completar el diagnóstico inicial en su primer ingreso a la plataforma. El sistema informa al estudiante sobre el uso de sus datos y solicita su consentimiento, presenta el cuestionario de línea base, almacena las respuestas asociadas al estudiante y calcula un nivel inicial estimado que sirve como punto de partida para la asignación de desafíos y del nivel de asistencia.
**Actores.** Estudiante: usuario que, en su primer ingreso a la plataforma, otorga su consentimiento informado y responde el cuestionario de línea base.
**Precondiciones.** El estudiante debe haber iniciado sesión en la plataforma por primera vez y no haber completado previamente el cuestionario de línea base. El cuestionario de línea base debe encontrarse disponible.
**Pos Condiciones.** Al finalizar correctamente, las respuestas del cuestionario quedan almacenadas y asociadas al estudiante, y su nivel inicial estimado queda registrado como punto de partida para la asignación de desafíos y del nivel de asistencia.
**Flujo Básico.** 
1. El estudiante inicia sesión en la plataforma por primera vez.
2. El sistema verifica que el estudiante no ha completado el cuestionario de línea base.
3. El sistema informa al estudiante sobre el uso de sus datos con fines de la tesis y solicita su consentimiento. [EX1]
4. El estudiante otorga su consentimiento informado.
5. El sistema presenta el cuestionario de línea base. [EX2]
6. El estudiante responde el cuestionario y envía sus respuestas. [EX3]
7. El sistema almacena las respuestas de línea base asociadas al estudiante. [EX4]
8. El sistema calcula, a partir de las respuestas, el nivel inicial estimado del estudiante. [EX4]
9. El sistema registra el nivel inicial estimado como punto de partida para la asignación de desafíos y del nivel de asistencia.
10. El sistema informa al estudiante que el diagnóstico inicial fue completado y el caso de uso termina.
**Excepciones.** 
[EX1]: El estudiante no otorga su consentimiento
El sistema no presenta el cuestionario ni almacena respuestas, informa que el consentimiento es necesario para completar el diagnóstico inicial y el caso de uso termina.
[EX2]: Cuestionario de línea base no disponible
El sistema informa al estudiante que el cuestionario no puede presentarse en ese momento y permite reintentar el acceso posteriormente.
[EX3]: Respuestas incompletas o no válidas
El sistema indica las preguntas que deben completarse o corregirse y no continúa con el registro hasta que las respuestas sean válidas.
[EX4]: Error al almacenar las respuestas o calcular el nivel inicial
El sistema informa al estudiante de forma controlada que no fue posible completar el diagnóstico, conserva las respuestas ingresadas y permite reintentar el envío.
**Requerimientos no funcionales.** Aplican: RNF-01, RNF-13, RNF-14, RNF-15, RNF-20, RNF-22, RNF-23

---
## CU07 - Gestionar el banco de desafíos

**Descripción.** Esta funcionalidad permite al administrador o docente gestionar el banco de desafíos de la plataforma. El usuario puede crear, editar y eliminar desafíos, así como clasificar cada uno por nivel de dificultad y por tema o unidad temática.
**Actores.** Administrador / Docente: usuario autenticado con rol habilitado que crea, edita, elimina y clasifica los desafíos del banco.
**Precondiciones.** El usuario debe haber iniciado sesión y contar con el rol de administrador o docente.
**Pos Condiciones.** Al finalizar correctamente, los cambios realizados sobre el banco de desafíos (creación, edición o eliminación) quedan almacenados y cada desafío conserva su clasificación por nivel de dificultad y tema o unidad temática, quedando disponible para su presentación a los estudiantes cuando corresponda.
**Flujo Básico.** 
1. El administrador o docente accede a la opción de gestión del banco de desafíos.
2. El sistema verifica el rol del usuario y muestra el listado de desafíos con su clasificación. [EX1]
3. El usuario selecciona la acción a realizar: crear, editar o eliminar un desafío.
4. Si el usuario crea un desafío, ingresa el enunciado, los recursos asociados, el criterio de validación de la respuesta, el nivel de dificultad y el tema o unidad temática. [EX2]
5. Si el usuario edita un desafío, selecciona el desafío, modifica sus datos o su clasificación por nivel de dificultad y tema o unidad temática, y confirma los cambios. [EX2] [EX3]
6. Si el usuario elimina un desafío, selecciona el desafío y confirma la eliminación. [EX3]
7. El sistema valida la información, aplica los cambios y los guarda en el banco de desafíos.
8. El sistema actualiza el listado de desafíos e informa el resultado de la operación.
9. El usuario puede realizar otra operación sobre el banco o finalizar, y el caso de uso termina.
**Excepciones.** 
[EX1]: Acceso no autorizado por rol
El sistema impide el acceso a la gestión del banco de desafíos cuando el usuario no cuenta con rol de administrador o docente y lo mantiene dentro de las opciones autorizadas.
[EX2]: Datos del desafío incompletos o no válidos
El sistema informa qué datos deben completarse o corregirse, incluyendo la clasificación por dificultad y tema, y no guarda los cambios hasta que la información sea válida.
[EX3]: Desafío no encontrado o no disponible
El sistema informa que el desafío seleccionado ya no existe o no está disponible para la operación solicitada y actualiza el listado de desafíos.
**Requerimientos no funcionales.** Aplican: RNF-01, RNF-05, RNF-07, RNF-08, RNF-13, RNF-14, RNF-15, RNF-20

---
## CU08 - Consultar reportes agregados de desempeño

**Descripción.** Esta funcionalidad permite al administrador o docente consultar reportes agregados sobre el uso de la plataforma y el desempeño general de los estudiantes. La información se presenta de forma consolidada y sin exponer datos personales identificables.
**Actores.** Administrador / Docente: usuario autenticado con rol habilitado que consulta los reportes agregados de uso y desempeño.
**Precondiciones.** El usuario debe haber iniciado sesión y contar con el rol de administrador o docente. Deben existir datos de uso y desempeño registrados para generar los reportes.
**Pos Condiciones.** Al finalizar el caso de uso, el usuario ha consultado los reportes agregados de uso de la plataforma y de desempeño general de los estudiantes. Esta consulta no modifica la información registrada.
**Flujo Básico.** 
1. El administrador o docente accede a la opción de reportes.
2. El sistema verifica el rol del usuario y presenta los reportes disponibles sobre el uso de la plataforma y el desempeño general de los estudiantes. [EX1]
3. El usuario selecciona el reporte que desea consultar.
4. El sistema consolida la información de forma agregada y anonimizada. [EX2] [EX3]
5. El sistema presenta el reporte solicitado.
6. El usuario revisa el reporte y, si lo requiere, consulta otro reporte disponible.
7. El usuario finaliza la consulta y el caso de uso termina.
**Excepciones.** 
[EX1]: Acceso no autorizado por rol
El sistema impide el acceso a los reportes cuando el usuario no cuenta con rol de administrador o docente y lo mantiene dentro de las opciones autorizadas.
[EX2]: No existen datos suficientes para el reporte
El sistema informa que no hay datos suficientes para generar el reporte solicitado y permite seleccionar otro reporte.
[EX3]: Error al generar el reporte
El sistema informa de forma controlada que el reporte no puede generarse en ese momento y permite reintentar la consulta.
**Requerimientos no funcionales.** Aplican: RNF-01, RNF-05, RNF-08, RNF-13, RNF-14, RNF-20, RNF-23