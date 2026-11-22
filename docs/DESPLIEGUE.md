# Despliegue gratuito: Neon + Render + Vercel

Producción = **Neon** (PostgreSQL) + **Render** (API FastAPI, sin Docker) + **Vercel** (frontend React). Todo en planes gratuitos.

```
Navegador ──► Vercel (frontend estático)
                 │  VITE_API_URL = https://<api>.onrender.com/api/v1
                 ▼
              Render (uvicorn, 1 worker) ──► Neon (PostgreSQL)
```

Orden: **1. Neon → 2. Render → 3. Vercel → 4. ajustar CORS en Render**. El orden importa: Render necesita la base, Vercel necesita la URL de Render y Render necesita la URL de Vercel (por eso CORS se ajusta al final).

Documentos relacionados: [migraciones](MIGRACIONES.md) · [manual del administrador](manual_administrador.md) · [README](../README.md).

## 0. Antes de empezar

- El repositorio está en GitHub (con `render.yaml` en la raíz y `frontend/vercel.json`). Nunca subas `.env` ni claves.
- Verifica que todo pasa en local: `python scripts/verificar.py`.
- Instala en tu equipo los **clientes de PostgreSQL** (`pg_dump`, `pg_restore`, `psql`) con la **misma versión mayor que tendrá Neon** (ver el recuadro del punto 1). Comprueba con `pg_dump --version`.

## 1. Neon (base de datos)

1. Crea una cuenta en neon.com y un proyecto nuevo.
2. **Versión de PostgreSQL:** elige la misma versión mayor que tus clientes `pg_dump`/`pg_restore` (por ejemplo 17).
3. **Región:** AWS US East 2 (Ohio), la misma región que usa `render.yaml` (`region: ohio`), para reducir latencia.
4. En el panel, botón **Connect**: copia la cadena de conexión **directa** (el host **sin** `-pooler`; si el panel ofrece la opción «Pooled connection», desactívala). Tiene esta forma:

```
postgresql://USUARIO:CLAVE@ep-xxxx.us-east-2.aws.neon.tech/neondb?sslmode=require
```

   Pégala tal cual en `DATABASE_URL`: la app cambia sola el prefijo a `postgresql+psycopg://`. La misma cadena sirve para la API, las migraciones y los respaldos. (La cadena con `-pooler` también funciona con la API, pero los respaldos y las migraciones deben usar la directa.)
5. Comprueba que conecta (opcional): `psql "CADENA" -c "select version();"`.

> **REGLA de versiones:** los clientes `pg_dump`/`pg_restore` deben tener la **misma versión mayor** que el servidor de Neon. Un cliente más nuevo que el servidor hace fallar `pg_restore`. Si ya creaste el proyecto con otra versión, instala clientes de esa versión o crea el proyecto de nuevo.

## 2. Render (API)

1. En render.com: **New → Blueprint**, conecta el repositorio y elige la rama. Render lee `render.yaml` y crea el servicio `sql-adaptativo-api` (plan Free, `rootDir: backend`).
2. Render pedirá los valores marcados `sync: false`:

| Variable | Qué poner |
|---|---|
| `DATABASE_URL` | La cadena directa de Neon (punto 1) |
| `CORS_ORIGINS` | Todavía no tienes la URL de Vercel: pon `http://localhost:5173` y la cambias en el punto 4 |
| `ADMIN_EMAIL` | Correo del primer administrador |
| `ADMIN_PASSWORD` | Contraseña larga (no la del ejemplo) |

3. `SECRET_KEY` y `ANON_SALT` los genera Render una sola vez (`generateValue`). **Guarda `ANON_SALT`** (Dashboard → Environment) en un gestor de contraseñas: si algún día corres `scripts/exportar_tesis.py` desde tu equipo contra Neon necesitas la misma sal, y **si cambia, cambian todos los seudónimos** de los reportes.
4. Render ejecuta el **build**: `pip install -r requirements.txt && alembic upgrade head` (crea o actualiza las tablas en Neon) y luego arranca `uvicorn`. Al arrancar, la app comprueba que la base esté en la última revisión y siembra los datos iniciales (idempotente).
5. Comprueba: abre `https://TU-SERVICIO.onrender.com/api/v1/health`. Debe responder `{"estado":"ok","base_datos":"ok",...}`. Si `base_datos` dice `no_disponible`, revisa `DATABASE_URL`.

Con `ENTORNO=produccion` la API **no arranca** (y el log lo explica) si falta `SECRET_KEY` o `ANON_SALT`, si `SECRET_KEY` tiene menos de 32 caracteres, si `DATABASE_URL` es SQLite o si la base no está en la última migración.

Por defecto Render vuelve a desplegar en cada `git push` a la rama enlazada, y cada despliegue ejecuta `alembic upgrade head`. Haz un respaldo (punto 8) antes de subir cambios de modelos.

## 3. Vercel (frontend)

1. En vercel.com: **Add New → Project**, importa el mismo repositorio.
2. **Root Directory:** `frontend`. El framework (Vite), el comando de build y la reescritura para la SPA ya están en `frontend/vercel.json`.
3. En **Environment Variables** define, **antes del primer despliegue**:

| Variable | Valor |
|---|---|
| `VITE_API_URL` | `https://TU-SERVICIO.onrender.com/api/v1` (con `/api/v1`, sin barra final) |

4. **Deploy.** Vite incrusta `VITE_API_URL` al compilar: si la cambias después, hay que volver a desplegar.
5. Anota la URL final (por ejemplo `https://sql-adaptativo.vercel.app`).

## 4. Ajustar CORS (último paso)

En Render → servicio → **Environment**, cambia `CORS_ORIGINS` por la URL **exacta** de Vercel, con `https` y **sin barra final**:

```
https://sql-adaptativo.vercel.app
```

Si usas más de un origen (por ejemplo un dominio propio), sepáralos con comas. Las URL de vista previa de Vercel (`...-git-rama-...vercel.app`) no quedan permitidas. Guarda: Render reinicia el servicio. Abre la URL de Vercel e inicia sesión con el administrador (si el navegador muestra errores de red o CORS, revisa este valor).

## 5. Primer ingreso

1. Entra con `ADMIN_EMAIL` / `ADMIN_PASSWORD` y abre **Usuarios** para convertir cuentas en docentes (ver el [manual del administrador](manual_administrador.md)).
2. La cuenta demo **no existe** en producción (`SEED_USUARIO_DEMO=false`).
3. Una vez creada la cuenta de administrador, `ADMIN_PASSWORD` ya no se usa (una cuenta existente no se modifica); puedes dejarla o vaciarla.

## 6. Variables por servicio

**Render** (API)

| Variable | Origen | Notas |
|---|---|---|
| `PYTHON_VERSION` | `render.yaml` (3.12.8) | Render exige versión completa; no uses 3.14 (no soportada) |
| `ENTORNO` | `render.yaml` (`produccion`) | Activa las validaciones de producción |
| `SEED_USUARIO_DEMO` | `render.yaml` (`false`) | La cuenta demo tiene contraseña conocida |
| `SECRET_KEY` | Generada por Render | Firma los JWT; no cambiarla (cierra todas las sesiones) |
| `ANON_SALT` | Generada por Render | Sal de los seudónimos; **no cambiarla** |
| `DATABASE_URL` | Tú (Neon) | Directa, con `?sslmode=require` |
| `CORS_ORIGINS` | Tú (Vercel) | URL exacta, sin barra final |
| `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Tú | Primer administrador |
| `DOMINIO_INSTITUCIONAL` | Opcional | Restringe el registro a correos de la universidad (p. ej. `unmsm.edu.pe`) |
| `LLM_PROVIDER`, `GROQ_API_KEY`, `GROQ_MODEL` | Opcional, en el panel | Sin ellas la ayuda funciona en modo demostración. La clave solo se escribe en el panel de Render |
| `DOCENTE_EMAIL`, `DOCENTE_PASSWORD` | Opcional | Docente de pruebas; en producción es mejor nombrarlos desde «Usuarios» |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Opcional (60) | Vigencia de la sesión |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_RECYCLE` | Opcional (5, 5, 280) | Pool de PostgreSQL; los valores por defecto sirven para el plan gratuito |
| `CREAR_TABLAS_AUTO` | No definir | Vacío = en producción la app no crea tablas (lo hace Alembic) |

**Vercel** (frontend): solo `VITE_API_URL`.

**Neon:** no tiene variables; solo entrega la cadena de conexión.

**Tu equipo** (`.env` en la raíz, solo desarrollo): ver `.env.example`. Para respaldos contra Neon no edites el `.env`: usa la variable de entorno de la sesión (punto 8).

## 7. Límites de los planes gratuitos

Datos revisados en la documentación oficial el 22 de noviembre de 2026; los planes cambian, vuelve a comprobarlos antes del piloto.

| Servicio | Límite | Efecto en el proyecto |
|---|---|---|
| **Render Free** | Se duerme tras 15 min sin tráfico entrante; despertar tarda alrededor de 1 minuto | La **primera visita tras la pausa es lenta** (arranque en frío de ~1 min: instala el entorno, comprueba el esquema y siembra). Mientras tanto Render muestra una página de carga |
| | 750 horas de instancia al mes por cuenta; al agotarlas se suspenden los servicios gratuitos hasta el mes siguiente | Un solo servicio gratuito 24/7 cabe (~720 h); no crees más servicios gratuitos en esa cuenta sin revisar el consumo |
| | Sistema de archivos efímero; puede reiniciarse en cualquier momento | No se guarda nada en disco (todo va a Neon); las sesiones sobreviven porque `SECRET_KEY` es fija |
| | Render puede suspender un servicio gratuito con un volumen inusualmente alto de tráfico iniciado por el servicio (por ejemplo, hacia una base externa) | Con una clase de estudiantes no se espera, pero está documentado |
| **Neon Free** | El cómputo se suspende tras 5 min sin consultas (fijo en el plan gratuito); al volver, reanuda normalmente en unos cientos de milisegundos | La primera consulta tras la pausa tarda un poco más; el pool usa `pool_pre_ping` y `pool_recycle` para no reutilizar conexiones muertas |
| | 100 CU-horas de cómputo por proyecto al mes, 1 GB de almacenamiento y 5 GB de transferencia pública | Si se agotan las CU-horas o la transferencia, el cómputo se suspende hasta el mes siguiente (los datos no se borran). Los respaldos cuentan para la transferencia |
| **Vercel Hobby** | Solo uso personal y no comercial; 100 GB de transferencia al mes | Adecuado para una tesis; si el proyecto pasara a un uso comercial/institucional de pago, requiere plan Pro |

**Recomendación para el día de una sesión:** abre `https://TU-SERVICIO.onrender.com/api/v1/health` unos 5 minutos antes para despertar la API y Neon. Si los estudiantes entran en tandas separadas por más de 15 minutos, la API vuelve a dormirse.

## 8. Respaldos y restauración con Neon

Los respaldos usan `scripts/respaldo.py` y `scripts/restaurar.py` desde **tu equipo**, con `pg_dump`/`pg_restore` (formato custom, archivo `.dump`). Detalles técnicos en la cabecera de cada script.

**Requisitos:** clientes de PostgreSQL con la misma versión mayor que Neon (**REGLA** del punto 1) y la cadena **directa** (si pegas la del `-pooler`, el script cambia al host directo). La clave viaja en `PGPASSWORD`, no en la línea de comandos.

**Respaldo** (en Git Bash, desde la raíz; la cadena se pide sin mostrarla y no se guarda en el historial ni en `.env`):

```bash
read -rsp "DATABASE_URL de Neon: " DATABASE_URL; echo
export DATABASE_URL
python scripts/respaldo.py            # crea respaldos/desafios_sql_AAAAMMDD_HHMMSS.dump y la verifica
unset DATABASE_URL
```

Haz uno **antes de cada sesión con estudiantes, después de cada una** y antes de desplegar cambios de modelos. Los `.dump` contienen datos personales: guárdalos fuera del repositorio (`*.dump` y `respaldos/` están en `.gitignore`), con acceso restringido, y bórralos al terminar el estudio.

**Restauración** (reemplaza los datos de Neon):

1. En Render, **Suspend** el servicio (así nadie escribe mientras restauras).
2. Con `DATABASE_URL` de Neon en la sesión (como arriba): `python scripts/restaurar.py respaldos/<copia>.dump`. El script verifica la copia, guarda antes una copia `antes_de_restaurar_…`, te pide **escribir el nombre de la base** para confirmar y restaura todo o nada (una sola transacción).
3. Si la copia es de un esquema anterior, aplica las migraciones: `cd backend && alembic upgrade head` (con la misma `DATABASE_URL`; ver [MIGRACIONES.md](MIGRACIONES.md)).
4. En Render, **Resume** el servicio y comprueba `/api/v1/health`.

**Ensayo recomendado antes del piloto:** restaura una copia en un PostgreSQL local (`docker compose up -d db`, con `DATABASE_URL` apuntando a `localhost:5433`) para comprobar que el `.dump` es utilizable sin tocar Neon.

## 9. Checklist antes de usar con estudiantes

- [ ] `https://TU-SERVICIO.onrender.com/api/v1/health` responde `ok` / `base_datos: ok`.
- [ ] La URL de Vercel carga, y el registro y el inicio de sesión funcionan (sin errores de CORS en la consola del navegador).
- [ ] `CORS_ORIGINS` es la URL exacta de Vercel, con `https` y sin barra final.
- [ ] `ENTORNO=produccion` y `SEED_USUARIO_DEMO=false` (no existe `estudiante@demo.edu`).
- [ ] `ANON_SALT` guardada fuera de Render y sin cambios desde que hay datos.
- [ ] El administrador entra, cambia el rol de los docentes en «Usuarios» y un docente ve el banco de desafíos.
- [ ] Recorrido completo con una cuenta de prueba: consentimiento, diagnóstico, un desafío (sandbox), una ayuda y «Progreso» (ver [PRUEBAS_MANUALES.md](PRUEBAS_MANUALES.md)).
- [ ] Un respaldo hecho **y** una restauración de ensayo en local comprobada.
- [ ] El texto del consentimiento (versión 1.1) lo validó la profesora o el comité ([PROVISIONALES.md](PROVISIONALES.md)).
- [ ] Si usas IA real: `LLM_PROVIDER=groq` y `GROQ_API_KEY` en Render, y una ayuda de prueba que salga con la etiqueta de IA.
- [ ] Los estudiantes están avisados de que la **primera carga puede tardar hasta ~1 minuto**; tú despertaste la API unos minutos antes (punto 7).
- [ ] El proyecto de Neon y el servicio de Render están a nombre de una cuenta que no vas a perder (y con la verificación en dos pasos activada).

## 10. Problemas frecuentes

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| El build de Render falla en `alembic upgrade head` | `DATABASE_URL` mal copiada, o Neon sin acceso | Revisa la cadena (`sslmode=require`); usa la directa, sin `-pooler` |
| La API no arranca: «faltan SECRET_KEY, ANON_SALT» o «no puede ser SQLite» | Variables ausentes o `DATABASE_URL` por defecto | Define las variables en Render (ver punto 6) |
| La API no arranca: «La BD está en la revisión … y la app espera …» | La base no está migrada | `cd backend && alembic upgrade head` con la `DATABASE_URL` de Neon (o `alembic stamp head` si ya tenía las tablas; ver [MIGRACIONES.md](MIGRACIONES.md)) |
| El navegador muestra error de red o CORS | `CORS_ORIGINS` incorrecto o `VITE_API_URL` sin `/api/v1` | Corrige y, si cambiaste `VITE_API_URL`, vuelve a desplegar en Vercel |
| Al recargar una página interna de Vercel sale 404 | Falta la reescritura de la SPA | Confirma que `frontend/vercel.json` está desplegado y que el Root Directory es `frontend` |
| Primera carga muy lenta | Arranque en frío de Render (y Neon despertando) | Normal en el plan gratuito; despierta la API antes de la sesión |
| `pg_restore` falla con errores de versión o de parámetros desconocidos | Clientes de otra versión mayor que el servidor | Aplica la REGLA de versiones del punto 1 |
| Las sesiones se cierran solas | `SECRET_KEY` cambió | No la regeneres; revisa que no se haya vuelto a crear el servicio |
