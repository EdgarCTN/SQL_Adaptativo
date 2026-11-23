# Migraciones de base de datos (Alembic)

El esquema de producción (Neon/PostgreSQL) lo crea y actualiza **Alembic**. En desarrollo y pruebas sigue funcionando `create_all` al arrancar, como antes.

| Entorno | Quién crea las tablas | Variable |
|---|---|---|
| Desarrollo (`ENTORNO=desarrollo`) | la app (`create_all` en el arranque) | `CREAR_TABLAS_AUTO` vacío = automático |
| Producción (`ENTORNO=produccion`) | `alembic upgrade head` (build de Render) | vacío = Alembic; la app **no** crea tablas |

En producción la app, al arrancar, comprueba que la BD esté en la última revisión; si no, falla con un mensaje que indica qué comando ejecutar. Los seeds idempotentes se siguen ejecutando en cada arranque.

Todos los comandos se ejecutan desde `backend/` y usan `DATABASE_URL` (la misma de la app; no hay URL en `alembic.ini`).

## 1. Generar la migración inicial (una sola vez, ya en el repo)

Se genera sobre una BD SQLite vacía y temporal, para que Alembic vea todas las tablas como nuevas:

```bash
cd backend
DATABASE_URL=sqlite:///alembic_tmp.db ENTORNO=desarrollo alembic revision --autogenerate -m "esquema inicial" --rev-id 0001
rm -f ../alembic_tmp.db   # temporal; no se versiona
```

Revisa `backend/alembic/versions/0001_esquema_inicial.py` y confirma que coincide con los modelos: `pytest tests/test_migraciones.py`.

## 2. BD nueva (Neon vacía)

```bash
cd backend
alembic upgrade head      # en Render ya lo hace el buildCommand
```

**Comprueba el motor en la primera línea del log:** debe decir `Context impl PostgresqlImpl`. Si dice `SQLiteImpl`, tu `DATABASE_URL` (en `.env` o en la sesión) sigue apuntando a SQLite y estás migrando la base equivocada. Para verificar a qué base apunta y que funciona: `python scripts/probar_bd.py` (o `bash scripts/bd.sh probar` para la local y `bash scripts/bd.sh neon-probar` para Neon).

## 3. BD existente que ya tiene las tablas (creadas con `create_all`)

No ejecutes `upgrade` (intentaría crear tablas que ya existen). Marca la BD como al día, **solo si su esquema es idéntico al de los modelos**:

```bash
cd backend
alembic stamp head
```

## 4. Cambiar un modelo (flujo normal)

1. Edita el modelo en `app/modules/*/models.py`.
2. `alembic revision --autogenerate -m "descripcion corta"` (sobre una BD al día con la última migración).
3. Revisa el archivo generado (Alembic no detecta renombres: los ve como borrar + crear).
4. `pytest tests/test_migraciones.py` y haz commit del archivo.
5. Al desplegar, Render ejecuta `alembic upgrade head` en el build.

## Notas

- Render free no tiene `preDeployCommand`; por eso la migración va en el `buildCommand`. Necesita `DATABASE_URL` disponible en el build (las variables del servicio lo están).
- Si Neon está suspendido, la primera conexión del build tarda unos segundos en despertarlo.
- Si la migración falla con el host `-pooler` de Neon, usa la cadena de conexión **directa** (sin `-pooler`) para ese comando.
- Revertir una migración: `alembic downgrade -1` (haz antes un respaldo; ver «Copias de seguridad» en DESPLIEGUE.md).
- `scripts/reset_db.py` se niega a ejecutarse con `ENTORNO=produccion` o con una BD que no sea local.
