# Probar que la base de datos funciona (PostgreSQL 18)

Guía con los comandos actualizados para **Git Bash**, desde la raíz del proyecto y con el entorno virtual activo
(`source backend/.venv/Scripts/activate`). Todos los comandos locales usan `scripts/bd.sh`, que fija la URL de la base
por sí mismo: **no depende de tu `.env`**.

## 1. Camino rápido (primera vez o después de actualizar)

```bash
bash scripts/bd.sh todo
```

Hace, en orden: levanta PostgreSQL 18 → `alembic upgrade head` + `alembic check` → siembra los datos iniciales →
ejecuta `scripts/probar_bd.py`. Al final debe decir `RESULTADO: TODO BIEN`.

Si venías de PostgreSQL 16 y el contenedor no arranca, el volumen viejo no es compatible con 18. Bórralo (**elimina los
datos locales**) y repite:

```bash
bash scripts/bd.sh reiniciar
```

## 2. Qué comprueba `probar_bd.py`

| # | Comprobación | Si falla |
|---|---|---|
| 1 | A qué base apunta (motor, host, origen de la URL). Avisa si es SQLite o un host `-pooler` de Neon | Cambia `DATABASE_URL` |
| 2 | Conexión y versión (`PostgreSQL 18.x`) | `bash scripts/bd.sh up` |
| 3 | La BD está en la última revisión de Alembic | `bash scripts/bd.sh migrar` |
| 4 | Existen todas las tablas y columnas de los modelos | Migrar o `reiniciar` |
| 5 | Hay datos iniciales (conceptos, desafíos, cuestionario, usuario demo) | `bash scripts/bd.sh sembrar` |
| 6 | Se puede escribir (inserta una fila y hace rollback; no deja nada) | Revisa permisos del usuario |

Un `[AVISO]` no es un error; un `[FALLO]` sí (y el script termina con código 1).

## 3. Comandos de uso diario

```bash
bash scripts/bd.sh up          # levanta PostgreSQL y espera a que esté listo
bash scripts/bd.sh version     # debe mostrar PostgreSQL 18.x
bash scripts/bd.sh psql        # consola psql ya conectada (la base es sql_adaptativo, con guion bajo)
bash scripts/bd.sh psql -c "select count(*) from conceptos;"
bash scripts/bd.sh probar      # verificación completa
bash scripts/bd.sh pruebas     # suite pytest contra PostgreSQL local
bash scripts/bd.sh estado      # contenedor, versión y tablas
```

Si usas `psql` a mano, recuerda `-d sql_adaptativo`; sin eso busca una base llamada como el usuario
(`sqladaptativo`) y falla con `database "sqladaptativo" does not exist`.

## 4. Que la app (uvicorn) use PostgreSQL

`bd.sh` no toca tu `.env`; la API sí lo lee. Para que use la base local de Docker, en `.env` deja **una sola** línea activa:

```
# DATABASE_URL=sqlite:///backend/desafios_sql.db
DATABASE_URL=postgresql+psycopg://sqladaptativo:sqladaptativo_dev@127.0.0.1:5433/sql_adaptativo
```

Después arranca la API (`cd backend && uvicorn app.main:app --reload --port 8000`) y abre
`http://localhost:8000/api/v1/health`: debe responder `"base_datos": "ok"`.

Para verificar a cuál base apunta tu `.env` sin ejecutar nada más: `python scripts/probar_bd.py`.

## 5. Probar Neon (sin editar el `.env`)

```bash
bash scripts/bd.sh neon-probar    # te pide la cadena sin mostrarla ni guardarla
bash scripts/bd.sh neon-migrar    # alembic upgrade head contra Neon (pide escribir SI)
```

Usa la cadena **directa** de Neon (host sin `-pooler`, con `?sslmode=require`). Si ya la tienes en una variable de la
sesión, evita pegarla cada vez: `export NEON_DATABASE_URL='postgresql://...'` (solo dura mientras la terminal esté abierta).

Orden recomendado: `neon-migrar` → `neon-probar` (punto 5 puede dar `[AVISO]` de base vacía: es normal hasta que la API
arranque en Render por primera vez y siembre los datos).

## 6. Problemas frecuentes

| Síntoma | Causa | Solución |
|---|---|---|
| `database "sqladaptativo" does not exist` | `psql` sin `-d` | Usa `bash scripts/bd.sh psql` o `-d sql_adaptativo` |
| `Context impl SQLiteImpl` al migrar | `DATABASE_URL` apunta a SQLite | Usa `bash scripts/bd.sh migrar` o corrige el `.env` |
| `table ... already exists` | Migraste sobre una base que ya tenía tablas (SQLite de desarrollo) | Apunta a una base nueva; ver `docs/MIGRACIONES.md` punto 3 |
| El contenedor `db` se reinicia o no arranca tras pasar a 18 | Volumen de PostgreSQL 16 | `bash scripts/bd.sh reiniciar` (borra datos locales) |
| Las conexiones tardan ~15 s (`Conexión correcta (15073 ms)`) y las pruebas son muy lentas | En Windows `localhost` se resuelve primero a IPv6 (`::1`), donde Docker no escucha, y espera el timeout antes de usar IPv4 | Usa `127.0.0.1` en lugar de `localhost` en `DATABASE_URL` (los archivos de este proyecto ya lo hacen) |
| `connection refused` en el puerto 5433 | Contenedor apagado | `bash scripts/bd.sh up` |
| `pg_restore`/`pg_dump` fallan por versión | Clientes distintos a la versión del servidor | Instala clientes 18 (`pg_dump --version`) |
