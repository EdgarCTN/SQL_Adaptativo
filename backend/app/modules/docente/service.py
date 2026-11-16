"""Banco de desafíos para el docente (entrega 12). Los desafíos con sesiones nunca se borran: se desactivan."""
import logging

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db import Base
from app.core.errores import ErrorApp
from app.core.reglas import cargar_reglas
from app.modules.desafios.models import Concepto, Desafio, SesionDesafio
from app.modules.docente.schemas import DesafioIn
from app.modules.docente.validacion import N_ERRORES_TIPICOS, TIPOS_AYUDA, problema, validar_contenido

log = logging.getLogger("app.docente")

DIFICULTADES = ("D1", "D2", "D3")
MSG_NO_EXISTE = "No encontramos ese desafío en el banco."
MSG_NO_GUARDADO = "El desafío no se guardó: corrige los problemas indicados."
MSG_ERROR_GUARDADO = "No pudimos guardar los cambios. Inténtalo de nuevo en unos segundos."
MSG_TITULO_REPETIDO = "Ya existe otro desafío con este título."
MSG_CONCEPTO = "Elige un concepto de la lista."
MSG_BORRADO = "Desafío eliminado del banco."
MSG_ACTIVADO = "Desafío activado: los estudiantes vuelven a verlo."
MSG_DESACTIVADO = "Desafío desactivado: los estudiantes ya no lo ven y su historial se conserva."
MSG_CONFIRMAR = (
    "Este desafío ya tiene {n} sesión(es) de estudiantes. Cambiar {campos} no modifica sus resultados anteriores, "
    "pero sí cómo se evaluarán los próximos intentos. Confirma para guardar."
)
_NOMBRE_CAMPO = {"solucion_referencia": "la solución", "sandbox_setup_sql": "el setup"}


# ---------- Utilidades ----------
def _tiempos_referencia() -> dict[str, int]:
    try:
        return {k: int(v) for k, v in cargar_reglas()["tiempo_referencia_seg"].items()}
    except (OSError, ValueError, KeyError, TypeError):
        log.warning("No se pudo leer tiempo_referencia_seg de reglas.json.")
        return {}


def _n_sesiones(db: Session, desafio_id: int) -> int:
    return db.scalar(select(func.count()).select_from(SesionDesafio).where(SesionDesafio.desafio_id == desafio_id)) or 0


def _n_dependencias(db: Session, desafio_id: int) -> int:
    """Filas de cualquier tabla que apunte a este desafío (sesiones, ayudas, omisiones, etc.)."""
    total = 0
    for tabla in Base.metadata.sorted_tables:
        for fk in tabla.foreign_keys:
            if fk.column.table.name == Desafio.__tablename__ and fk.column.name == "id":
                total += db.scalar(select(func.count()).select_from(tabla).where(fk.parent == desafio_id)) or 0
    return total


def _concepto_out(c: Concepto) -> dict:
    return {"codigo": c.codigo, "nombre": c.nombre}


def _fila(d: Desafio, c: Concepto, n_sesiones: int) -> dict:
    return {
        "id": d.id,
        "titulo": d.titulo,
        "concepto": _concepto_out(c),
        "dificultad": d.dificultad,
        "tiempo_referencia_seg": d.tiempo_referencia_seg,
        "activo": bool(d.activo),
        "n_sesiones": n_sesiones,
        "creado_en": d.creado_en,
    }


def _ayudas_salida(ayudas) -> dict:
    ayudas = ayudas if isinstance(ayudas, dict) else {}
    salida = {}
    for tipo in TIPOS_AYUDA:
        a = ayudas.get(tipo) if isinstance(ayudas.get(tipo), dict) else {}
        salida[tipo] = {"mensaje": str(a.get("mensaje") or ""), "codigo_sql": a.get("codigo_sql") or None}
    return salida


def _errores_salida(errores) -> list[dict]:
    return [
        {"descripcion": str(e.get("descripcion") or ""), "ejemplo": str(e.get("ejemplo") or "")}
        for e in (errores if isinstance(errores, list) else [])
        if isinstance(e, dict)
    ]


def _detalle(db: Session, d: Desafio) -> dict:
    c = db.get(Concepto, d.concepto_id)
    return {
        **_fila(d, c, _n_sesiones(db, d.id)),
        "enunciado": d.enunciado,
        "recursos": [str(r) for r in (d.recursos or [])],
        "esquema_sql": d.esquema_sql,
        "sandbox_setup_sql": d.sandbox_setup_sql,
        "solucion_referencia": d.solucion_referencia,
        "errores_tipicos": _errores_salida(d.errores_tipicos),
        "ayudas_respaldo": _ayudas_salida(d.ayudas_respaldo),
    }


def _normalizar(datos: DesafioIn) -> dict:
    """Recorta textos y deja los campos en la forma en que se guardan."""
    ayudas = {}
    for tipo in TIPOS_AYUDA:
        a = getattr(datos.ayudas_respaldo, tipo)
        ayudas[tipo] = {"mensaje": a.mensaje.strip(), "codigo_sql": (a.codigo_sql or "").strip() or None}
    return {
        "titulo": datos.titulo.strip(),
        "enunciado": datos.enunciado.strip(),
        "recursos": [r.strip() for r in datos.recursos if r.strip()],
        "concepto": datos.concepto.strip(),
        "dificultad": datos.dificultad.strip().upper(),
        "esquema_sql": datos.esquema_sql.strip(),
        "sandbox_setup_sql": datos.sandbox_setup_sql.strip(),
        "solucion_referencia": datos.solucion_referencia.strip(),
        "errores_tipicos": [{"descripcion": e.descripcion.strip(), "ejemplo": e.ejemplo.strip()} for e in datos.errores_tipicos],
        "ayudas_respaldo": ayudas,
        "tiempo_referencia_seg": datos.tiempo_referencia_seg,
    }


def _problemas(db: Session, n: dict, propio_id: int | None) -> list[dict]:
    """Validación completa: campos básicos, concepto, título único y sandbox. Un desafío con problemas no se guarda."""
    p = validar_contenido(n)
    if n["titulo"]:
        otro = db.scalar(
            select(Desafio.id).where(func.lower(Desafio.titulo) == n["titulo"].lower(), Desafio.id != (propio_id or 0))
        )
        if otro is not None:
            p.insert(0, problema("titulo", MSG_TITULO_REPETIDO))
    if not n["concepto"] or db.scalar(select(Concepto.id).where(Concepto.codigo == n["concepto"])) is None:
        p.append(problema("concepto", MSG_CONCEPTO))
    return p


def _lanzar_si_hay_problemas(problemas: list[dict]) -> None:
    if problemas:
        raise ErrorApp(MSG_NO_GUARDADO, 422, extra={"detalles": problemas})


def _obtener(db: Session, desafio_id: int) -> Desafio:
    d = db.get(Desafio, desafio_id)
    if d is None:
        raise ErrorApp(MSG_NO_EXISTE, 404)
    return d


def _aplicar(db: Session, d: Desafio, n: dict) -> None:
    d.titulo = n["titulo"]
    d.enunciado = n["enunciado"]
    d.recursos = n["recursos"]
    d.concepto_id = db.scalar(select(Concepto.id).where(Concepto.codigo == n["concepto"]))
    d.dificultad = n["dificultad"]
    d.esquema_sql = n["esquema_sql"]
    d.sandbox_setup_sql = n["sandbox_setup_sql"]
    d.solucion_referencia = n["solucion_referencia"]
    d.errores_tipicos = n["errores_tipicos"]
    d.ayudas_respaldo = n["ayudas_respaldo"]
    d.tiempo_referencia_seg = n["tiempo_referencia_seg"] or _tiempos_referencia().get(n["dificultad"], 600)


def _guardar(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:  # título repetido en una carrera entre dos docentes
        db.rollback()
        raise ErrorApp(MSG_NO_GUARDADO, 422, extra={"detalles": [problema("titulo", MSG_TITULO_REPETIDO)]})
    except SQLAlchemyError:
        db.rollback()
        log.exception("No se pudo guardar el desafío")
        raise ErrorApp(MSG_ERROR_GUARDADO, 503)


# ---------- Lectura ----------
def opciones(db: Session) -> dict:
    conceptos = db.scalars(select(Concepto).order_by(Concepto.id))
    return {
        "conceptos": [_concepto_out(c) for c in conceptos],
        "dificultades": list(DIFICULTADES),
        "tiempos_referencia": _tiempos_referencia(),
        "n_errores_tipicos": N_ERRORES_TIPICOS,
    }


def listar(db: Session, concepto: str | None, dificultad: str | None, estado: str | None, q: str | None) -> dict:
    sesiones = (
        select(SesionDesafio.desafio_id.label("did"), func.count().label("n")).group_by(SesionDesafio.desafio_id).subquery()
    )
    consulta = (
        select(Desafio, Concepto, func.coalesce(sesiones.c.n, 0))
        .join(Concepto, Concepto.id == Desafio.concepto_id)
        .outerjoin(sesiones, sesiones.c.did == Desafio.id)
        .order_by(Concepto.id, Desafio.dificultad, Desafio.id)
    )
    if concepto:
        consulta = consulta.where(Concepto.codigo == concepto)
    if dificultad in DIFICULTADES:
        consulta = consulta.where(Desafio.dificultad == dificultad)
    if estado == "activos":
        consulta = consulta.where(Desafio.activo.is_(True))
    elif estado == "inactivos":
        consulta = consulta.where(Desafio.activo.is_(False))
    if q and q.strip():
        consulta = consulta.where(func.lower(Desafio.titulo).contains(q.strip().lower(), autoescape=True))
    filas = [_fila(d, c, int(n)) for d, c, n in db.execute(consulta)]
    return {"total": len(filas), "desafios": filas}


def detalle(db: Session, desafio_id: int) -> dict:
    return _detalle(db, _obtener(db, desafio_id))


# ---------- Escritura ----------
def validar(db: Session, datos: DesafioIn, desafio_id: int | None) -> dict:
    problemas = _problemas(db, _normalizar(datos), desafio_id)
    return {"valido": not problemas, "problemas": problemas}


def crear(db: Session, datos: DesafioIn) -> dict:
    n = _normalizar(datos)
    _lanzar_si_hay_problemas(_problemas(db, n, None))
    d = Desafio(activo=True)
    _aplicar(db, d, n)
    db.add(d)
    _guardar(db)
    db.refresh(d)
    return _detalle(db, d)


def actualizar(db: Session, desafio_id: int, datos: DesafioIn) -> dict:
    d = _obtener(db, desafio_id)
    n = _normalizar(datos)
    _lanzar_si_hay_problemas(_problemas(db, n, d.id))
    cambiados = [
        campo for campo in ("solucion_referencia", "sandbox_setup_sql") if (getattr(d, campo) or "").strip() != n[campo]
    ]
    usadas = _n_sesiones(db, d.id) if cambiados else 0
    if usadas and not datos.confirmar_cambio:
        texto = " y ".join(_NOMBRE_CAMPO[c] for c in cambiados)
        raise ErrorApp(MSG_CONFIRMAR.format(n=usadas, campos=texto), 409)
    _aplicar(db, d, n)
    _guardar(db)
    db.refresh(d)
    return _detalle(db, d)


def cambiar_activo(db: Session, desafio_id: int, activo: bool) -> dict:
    d = _obtener(db, desafio_id)
    if bool(d.activo) != activo:
        d.activo = activo
        _guardar(db)
    return {"ok": True, "mensaje": MSG_ACTIVADO if activo else MSG_DESACTIVADO}


def eliminar(db: Session, desafio_id: int) -> dict:
    d = _obtener(db, desafio_id)
    if _n_dependencias(db, d.id) > 0:
        raise ErrorApp(
            "Este desafío ya tiene historial de estudiantes, así que no se puede borrar. "
            "Desactívalo: dejará de verse para los estudiantes y su historial se conserva.",
            409,
        )
    try:
        db.delete(d)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        log.exception("No se pudo borrar el desafío")
        raise ErrorApp(MSG_ERROR_GUARDADO, 503)
    return {"ok": True, "mensaje": MSG_BORRADO}
