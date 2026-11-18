# PRUEBAS MANUALES (RNF-14, RNF-15, RNF-20)

Se hacen una vez antes del piloto y de nuevo tras cambios grandes de la interfaz. Marca cada casilla; anota fecha, navegador, versión y lo que falle (con captura). Una prueba pasa si no hay texto cortado, scroll horizontal de la página, botones inalcanzables, pantallas en blanco ni errores técnicos visibles.

## 0. Preparación
- [ ] Base limpia: `python scripts/reset_db.py`. Define `DOCENTE_EMAIL`/`DOCENTE_PASSWORD` y `ADMIN_EMAIL`/`ADMIN_PASSWORD` en `.env`.
- [ ] Servidor en `http://localhost:8000/docs` abre y `/api/v1/health` responde `ok`; interfaz en `http://localhost:5173`.
- [ ] Cuatro cuentas: estudiante demo (`estudiante@demo.edu`), una nueva por registro, docente y administrador.
- [ ] Hoja de resultados: copia la tabla de la sección 4.

## 1. Diseño responsivo (RNF-14) — tres anchos
Prueba en Chrome con las herramientas de desarrollo (F12, modo dispositivo, ancho personalizado): **1366 px** (laptop), **768 px** (tableta) y **375 px** (móvil). En cada ancho recorre:

| Pantalla | Qué comprobar |
|---|---|
| Login y Registro | Formulario completo visible; mensajes de error legibles |
| Consentimiento y Diagnóstico | Texto sin cortes; botones «Acepto y continuar» y de navegación alcanzables; opciones de confianza (1 a 5) tocables |
| Desafíos (lista) | Filtro por concepto; tarjetas sin desbordar; «Empieza aquí» visible |
| Desafío (resolución) | Enunciado, esquema, editor, «Enviar», «Abandonar», «Omitir» y panel de ayuda accesibles; tablas de resultado con scroll propio, no de la página |
| Progreso | Resumen, gráficos (no se cortan), tabla de historial y filtros de fechas |
| Notificaciones y campana | El panel de la campana cabe en pantalla |
| Perfil | Ambos formularios |
| Banco de desafíos y formulario (docente) | Tabla con scroll propio; formulario completo |
| Reportes | Tablas con scroll propio; botones de descarga |
| Usuarios (administrador) | Tabla y paginación |

- [ ] A 768 px o menos el menú lateral se oculta y aparece el botón **Menú**, que lo abre y cierra.
- [ ] A 375 px no hay scroll horizontal de la página en ninguna pantalla.
- [ ] Zoom del navegador al 150 %: nada queda inutilizable.

## 2. Navegadores (RNF-20)
Repite en **Chrome, Edge, Firefox y Safari** (Safari requiere un Mac o iPhone; si no hay, anótalo como no probado). En cada uno completa el recorrido corto:
- [ ] Registro, consentimiento y diagnóstico completo (recarga a mitad: el avance se conserva).
- [ ] Un desafío: Comenzar, enviar una consulta incorrecta y otra correcta, pedir ayuda y valorarla.
- [ ] Omitir un desafío y abandonar otro.
- [ ] Campana de notificaciones, Progreso con gráficos e historial filtrado.
- [ ] Cerrar sesión e intentar volver con el botón «Atrás»: pide iniciar sesión.
- [ ] Como docente: crear, validar, desactivar y activar un desafío. Como administrador: cambiar un rol (con confirmación).
- [ ] Reportes: se descarga el CSV y el ZIP.
- [ ] Consola del navegador sin errores rojos durante el recorrido.

## 3. Cada acción da una respuesta visible (RNF-15)
Para cada acción debe verse, sin recargar, un cambio claro: botón en estado ocupado, mensaje, aviso o cambio de pantalla. Ninguna acción puede quedar «muda».

| Acción | Respuesta esperada |
|---|---|
| Registrarse con correo repetido o contraseña débil | Error junto al campo |
| Iniciar sesión con datos incorrectos | Mensaje único, sin revelar cuál dato falla |
| Aceptar o rechazar el consentimiento | «Guardando…» y paso siguiente; si rechaza, aviso con opciones |
| Enviar una respuesta del diagnóstico | Avance de la barra de progreso; resultado final |
| Comenzar un desafío | «Iniciando…» y editor habilitado |
| Enviar una consulta (correcta, incorrecta, con error de sintaxis, vacía) | «Enviando…» y resultado; vacío: «Escribe tu consulta antes de enviar.» |
| Pedir ayuda | «Buscando ayuda…» y tarjeta con su etiqueta (IA, respaldo o demostración) |
| Valorar una ayuda | «Gracias por tu valoración.» |
| Ver una solución completa | Aviso de que el desafío se marcará como no resuelto |
| Abandonar / Omitir | Diálogo de confirmación y, después, resultado |
| Cambio de nivel de ayuda | Aviso en pantalla, contador en la campana y entrada en Notificaciones |
| «Mantener la ayuda» / «Sí, menos ayuda» | Confirmación visible |
| Marcar notificaciones como leídas | El contador baja |
| Guardar nombre o contraseña en Perfil | Mensaje de éxito o de error |
| Cerrar sesión | «Saliendo…» y regreso al login |
| Docente: validar, guardar, activar, desactivar, eliminar | Mensajes de éxito o errores por campo; diálogo antes de eliminar |
| Administrador: cambiar rol, activar o desactivar | Diálogo y mensaje de éxito; error si es su propia cuenta |
| Reportes: cambiar fechas, descargar | Tablas actualizadas; «Descargando…» |
| Apagar el servidor y repetir una acción | Mensaje amable con «Reintentar», nunca una pantalla en blanco |
| Escribir una dirección inexistente | Página 404; una ruta de otro rol: página 403 |

## 4. Hoja de resultados
| Fecha | Navegador y versión | Ancho | Resultado | Observaciones |
|---|---|---|---|---|
| | | | | |

## 5. Antes del piloto (revisión de datos y seguridad)
- [ ] Tras el recorrido, abrir un CSV de **Reportes**: no aparece ningún nombre, correo ni código SQL; las columnas son solo seudónimo y datos de uso.
- [ ] Un estudiante recibe error 403 al abrir `/reportes` o `/admin/usuarios` escribiendo la dirección.
- [ ] El consentimiento muestra la versión «1.1» y la profesora o el comité lo validó.
- [ ] `SEED_USUARIO_DEMO=false`, `ANON_SALT` y `SECRET_KEY` definidos en el `.env` del servidor.
- [ ] Sin clave de IA todo funciona en modo demostración (ayudas rotuladas «Ayuda de demostración»); con la clave nueva la ayuda dice «Generada por IA».
- [ ] No hay secretos en el repositorio ni en su historial: `git log --all -p -S"gsk_"` y `-S"sk-ant"` no devuelven nada; `.env` figura en `.gitignore`.
- [ ] Copia de seguridad hecha y **restauración probada** (`docs/manual_administrador.md`).
