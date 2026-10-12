"""Resumen de progreso del estudiante (solo lectura sobre datos que ya guardan las demás entregas)."""
import logging

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errores import ErrorApp
from app.modules.asistencia.config_llm import cargar_mensajes_fijos
from app.modules.asistencia.models import SolicitudAyuda
from app.modules.auth.models import Usuario
from app.modules.desafios.models import Concepto, Desafio, SesionDesafio
from app.modules.linea_base.models import NivelSoporte
from app.modules.motor_retiro.models import HistorialNivel
from app.modules.motor_retiro.niveles import NS_POR_DEFECTO

log = logging.getLogger("app.progreso")

MAX_CAMBIOS = 10
TIPOS_AYUDA = ("AY1", "AY2", "AY3", "AY4")
MSG_ERROR = "No pudimos cargar tu progreso en este momento. Inténtalo de nuevo."
MSG_SUGERENCIA = "Todavía no tienes actividad. Resuelve tu primer desafío para empezar a ver tu progreso."


def _texto_cambio(regla: str, concepto: str, ns_anterior: int, ns_nuevo: int) -> str:
    """Texto para el estudiante: primer mensaje fijo de la regla; si no hay, uno genérico."""
    try:
        for m in cargar_mensajes_fijos()["mensajes"].values():
            if regla in (m.get("regla") or []) and m.get("texto"):
                return m["texto"].replace("{{concepto}}", concepto)
    except (KeyError, OSError, ValueError, TypeError, AttributeError):
        pass
    return f"Tu nivel de ayuda en {concepto} pasó de {ns_anterior} a {ns_nuevo}."


def resumen(db: Session, usuario: Usuario) -> dict:
    try:
        return _resumen(db, usuario)
    except SQLAlchemyError:
        log.exception("No se pudo calcular el resumen de progreso (usuario %s)", usuario.id)
        raise ErrorApp(MSG_ERROR, 503)


def _resumen(db: Session, usuario: Usuario) -> dict:
    uid = usuario.id
    conceptos = list(db.scalars(select(Concepto).order_by(Concepto.id)))

    # Desafíos resueltos: distintos, y sin contar los que terminaron como NR (vio la solución completa)
    filas = db.execute(
        select(Desafio.concepto_id, SesionDesafio.desafio_id)
        .join(Desafio, Desafio.id == SesionDesafio.desafio_id)
        .where(
            SesionDesafio.usuario_id == uid,
            SesionDesafio.estado == "resuelto",
            (SesionDesafio.resultado_cierre.is_(None)) | (SesionDesafio.resultado_cierre != "NR"),
        )
        .distinct()
    ).all()
    resueltos_por_concepto: dict[int, int] = {}
    for concepto_id, _ in filas:
        resueltos_por_concepto[concepto_id] = resueltos_por_concepto.get(concepto_id, 0) + 1

    disponibles = db.scalar(select(func.count()).select_from(Desafio).where(Desafio.activo.is_(True))) or 0
    abandonadas = (
        db.scalar(
            select(func.count())
            .select_from(SesionDesafio)
            .where(SesionDesafio.usuario_id == uid, SesionDesafio.estado == "abandonado")
        )
        or 0
    )

    ns_guardado = {
        c_id: int(ns)
        for c_id, ns in db.execute(
            select(NivelSoporte.concepto_id, NivelSoporte.ns).where(NivelSoporte.usuario_id == uid)
        )
    }
    niveles = [
        {
            "codigo": c.codigo,
            "nombre": c.nombre,
            "ns": ns_guardado.get(c.id, NS_POR_DEFECTO),
            "desafios_resueltos": resueltos_por_concepto.get(c.id, 0),
        }
        for c in conceptos
    ]

    ayudas = {t: 0 for t in TIPOS_AYUDA}
    for tipo, n in db.execute(
        select(SolicitudAyuda.tipo_ayuda, func.count()).where(SolicitudAyuda.usuario_id == uid).group_by(SolicitudAyuda.tipo_ayuda)
    ):
        if tipo in ayudas:
            ayudas[tipo] = int(n)
    ayudas["total"] = sum(ayudas[t] for t in TIPOS_AYUDA)

    nombres = {c.id: c.nombre for c in conceptos}
    cambios = [
        {
            "concepto": nombres.get(h.concepto_id, "Concepto"),
            "ns_anterior": h.ns_anterior,
            "ns_nuevo": h.ns_nuevo,
            "texto": _texto_cambio(h.regla, nombres.get(h.concepto_id, "este tema"), h.ns_anterior, h.ns_nuevo),
            "fecha": h.creado_en,
        }
        for h in db.scalars(
            select(HistorialNivel)
            .where(HistorialNivel.usuario_id == uid)
            .order_by(HistorialNivel.creado_en.desc(), HistorialNivel.id.desc())
            .limit(MAX_CAMBIOS)
        )
    ]

    total_resueltos = len(filas)
    hubo_sesion = db.scalar(select(SesionDesafio.id).where(SesionDesafio.usuario_id == uid).limit(1)) is not None
    sin_actividad = not hubo_sesion and ayudas["total"] == 0 and not cambios
    return {
        "sin_actividad": sin_actividad,
        "sugerencia": MSG_SUGERENCIA if sin_actividad else None,
        "desafios_resueltos": total_resueltos,
        "desafios_disponibles": int(disponibles),
        "sesiones_abandonadas": int(abandonadas),
        "diagnostico_completado": bool(usuario.linea_base_completada),
        "niveles": niveles,
        "ayudas": ayudas,
        "cambios_recientes": cambios,
    }
