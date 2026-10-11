# ESTADO DEL PROYECTO
## Progreso
Última entrega completada: 1. Siguiente: 2. Pendiente a medias: nada.
## BD (una línea por tabla)
usuarios(id, nombre, correo*unica, hash_password, rol[estudiante|docente|administrador], activo, creado_en, linea_base_completada)
conceptos(id, codigo*unica, nombre, prerrequisito_id→conceptos.id nullable; vacío) — 10 códigos sembrados
## API (una línea por endpoint; prefijo /api/v1)
GET /health [público] → estado, base_datos, fecha
POST /auth/registro [público] → UsuarioOut (201; siempre rol estudiante; 409 correo repetido; 422 datos/dominio)
POST /auth/login [público] → access_token, token_type, expira_en(seg), usuario{id,nombre,correo,rol,activo,creado_en,linea_base_completada}
POST /auth/logout [autenticado] → ok, mensaje (sin revocación)
GET /auth/yo [autenticado] → UsuarioOut
GET /perfil [autenticado] → UsuarioOut
PUT /perfil [autenticado] body{nombre?, contrasena_actual?, contrasena_nueva?} → UsuarioOut
Errores: JSON {error:true, mensaje, detalles?[{campo,mensaje}]}. Token: cabecera Authorization: Bearer.
## Frontend
Aún no existe (Entrega 2). Backend con CORS desde CORS_ORIGINS (http://localhost:5173).
## Nombres que otras entregas usan
core/config.py: settings (database_url, secret_key, access_token_expire_minutes, cors_lista, dominios_permitidos, demo_email, demo_password), RAIZ
core/db.py: Base, engine, SessionLocal, get_db, init_db, cargar_modelos (añadir aquí los modelos nuevos), UTCDateTime, ahora_utc
core/errores.py: ErrorApp(mensaje, status_code, headers), registrar_manejadores
core/seguridad.py: hashear_password, verificar_password, crear_token, decodificar_token
modules/auth/deps.py: usuario_actual, requiere_rol(*roles) · modules/auth/models.py: Usuario, Rol
modules/desafios/models.py: Concepto (los modelos de desafíos van aquí)
seeds/seed.py: sembrar_todo(db) (añadir seeds nuevos ahí), sembrar_conceptos, sembrar_usuario_demo
Usuario demo: estudiante@demo.edu / DEMO_PASSWORD (.env.example: Demo12345!)
Tests: backend/tests/conftest.py (fixtures client, db; helpers registrar, login, token_de, cabecera; BD temporal)
scripts: verificar.py (pytest + npm run build si existe frontend/), reset_db.py
Variables .env: DATABASE_URL, SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES, CORS_ORIGINS, DOMINIO_INSTITUCIONAL, SEED_USUARIO_DEMO, DEMO_EMAIL, DEMO_PASSWORD
## Decisiones nuevas para DECISIONES.md
- Sin Redis ni revocación de JWT: logout solo responde OK y el cliente descarta el token (CU01 pide invalidarlo; pendiente de infraestructura). El token lleva jti para una futura revocación.
- SECRET_KEY vacía = clave aleatoria temporal (las sesiones se pierden al reiniciar/recargar); se recomienda fijarla en .env.
- create_all y seeds idempotentes corren al iniciar el servidor; SEED_USUARIO_DEMO=false desactiva el usuario demo.
- GET/PUT /perfil disponibles para cualquier rol autenticado (CU01 lo describe para el estudiante).
- Contraseña: 8-128 caracteres con al menos una letra y un número. Correo guardado en minúsculas.
- Login con mismo mensaje para correo inexistente, contraseña errónea o cuenta inactiva.
- Concepto vive en modules/desafios/models.py; prerrequisito_id queda vacío.
- Fechas UTC con tipo UTCDateTime (SQLite pierde la zona; se restituye al leer).
## Problemas conocidos
Verificado solo con Python 3.12 en Linux; no probado aún en Git Bash/Windows con 3.13.
