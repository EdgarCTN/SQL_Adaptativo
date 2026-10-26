"""Desafío de verificación de R7: elegir, asignar y completar.

Otras entregas: `es_verificacion_pendiente` dice si un desafío es hoy una verificación del estudiante (la ayuda
automática de la entrega 8 no debe ofrecerse en ese caso). Una verificación resuelta como SA cuenta como el primero
de los 3 desafíos limpios de R2 sin trabajo extra: es una sesión cerrada más de la ventana (entrega 5).
"""
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import ahora_utc
from app.modules.desafios.models import Concepto, Desafio, SesionDesafio
from app.modules.motor_retiro.models import Verificacion
from app.modules.motor_retiro.omisiones import (
    ORDEN_DIFICULTAD,
    DesafioRef,
    contar_muy_facil,
    hay_verificacion_pendiente,
    ids_resueltos,
    ultima_omision_id,
)

log = logging.getLogger("app.motor")


@dataclass(frozen=True)
class VerificacionAsignada:
    concepto: str
    desafio_id: int
    titulo: str
    dificultad: str


def elegir_desafio(db: Session, usuario_id: int, concepto_id: int, omitido_id: int | None = None) -> DesafioRef | None:
    """Desafío activo del concepto, sin resolver y sin sesión en curso (PROVISIONAL).

    Orden de preferencia: distinto del recién omitido, de dificultad igual o mayor que la de este, el más básico de
    ellos, el de menor id. Si el único candidato es el recién omitido (concepto con un solo desafío), se usa ese.
    """
    activos = list(db.scalars(select(Desafio).where(Desafio.concepto_id == concepto_id, Desafio.activo.is_(True))))
    resueltos = ids_resueltos(db, usuario_id)
    en_curso = set(
        db.scalars(
            select(SesionDesafio.desafio_id).where(
                SesionDesafio.usuario_id == usuario_id, SesionDesafio.estado == "en_curso"
            )
        )
    )
    candidatos = [d for d in activos if d.id not in resueltos and d.id not in en_curso]
    if not candidatos:
        return None
    omitido = next((d for d in activos if d.id == omitido_id), None)
    nivel = ORDEN_DIFICULTAD.get(omitido.dificultad, 0) if omitido else 0
    candidatos.sort(
        key=lambda d: (d.id == omitido_id, ORDEN_DIFICULTAD.get(d.dificultad, 99) < nivel, ORDEN_DIFICULTAD.get(d.dificultad, 99), d.id)
    )
    d = candidatos[0]
    return DesafioRef(d.id, d.titulo, d.dificultad, d.concepto_id)


def asignar(
    db: Session, usuario_id: int, concepto_id: int, origen: str, omitido_id: int | None = None
) -> VerificacionAsignada | None:
    """Crea la verificación (sin confirmar la transacción) y reinicia el contador de R7. None si no hay desafío."""
    d = elegir_desafio(db, usuario_id, concepto_id, omitido_id)
    if d is None:
        log.warning("R7: no hay desafío disponible para verificar el concepto %s (usuario %s)", concepto_id, usuario_id)
        return None
    db.add(
        Verificacion(
            usuario_id=usuario_id, concepto_id=concepto_id, desafio_id=d.id, origen=origen,
            ultima_omision_id=ultima_omision_id(db, usuario_id, concepto_id), estado="pendiente", creada_en=ahora_utc(),
        )
    )
    nombre = db.scalar(select(Concepto.nombre).where(Concepto.id == concepto_id)) or ""
    return VerificacionAsignada(nombre, d.id, d.titulo, d.dificultad)


def asignar_tras_linea_base(db: Session, usuario_id: int, m_por_concepto: dict, reglas: dict) -> list[VerificacionAsignada]:
    """R0/R7: concepto con ≥ 2 ítems en la línea base y todos omitidos por «Muy fácil» → verificación al terminar el diagnóstico.

    Un concepto con 1 solo ítem queda con el contador en 1: la verificación llega con la siguiente omisión «Muy fácil».
    Confirma la transacción. Sin desafío disponible para un concepto, ese concepto se omite.
    """
    umbral = int(reglas["r7_muy_facil"]["omisiones_para_verificacion"])
    conceptos = {c.codigo: c.id for c in db.scalars(select(Concepto))}
    asignadas: list[VerificacionAsignada] = []
    for codigo, info in m_por_concepto.items():
        concepto_id = conceptos.get(codigo)
        if concepto_id is None or not info.get("todas_muy_facil") or int(info.get("n_items") or 0) < umbral:
            continue
        if hay_verificacion_pendiente(db, usuario_id, concepto_id) or contar_muy_facil(db, usuario_id, concepto_id) < umbral:
            continue
        v = asignar(db, usuario_id, concepto_id, "linea_base")
        if v is not None:
            asignadas.append(v)
    db.commit()
    return asignadas


def verificacion_pendiente(db: Session, usuario_id: int, desafio_id: int) -> Verificacion | None:
    return db.scalar(
        select(Verificacion)
        .where(Verificacion.usuario_id == usuario_id, Verificacion.desafio_id == desafio_id, Verificacion.estado == "pendiente")
        .order_by(Verificacion.id.desc())
        .limit(1)
    )


def es_verificacion_pendiente(db: Session, usuario_id: int, desafio_id: int) -> bool:
    return verificacion_pendiente(db, usuario_id, desafio_id) is not None


def ids_verificacion_pendiente(db: Session, usuario_id: int) -> set[int]:
    return set(
        db.scalars(
            select(Verificacion.desafio_id).where(Verificacion.usuario_id == usuario_id, Verificacion.estado == "pendiente")
        )
    )


def completar_si_corresponde(db: Session, sesion: SesionDesafio) -> None:
    """Al cerrarse una sesión del desafío de una verificación pendiente (iniciada tras la asignación), la completa. Sin commit."""
    v = verificacion_pendiente(db, sesion.usuario_id, sesion.desafio_id)
    if v is None or sesion.inicio is None or sesion.inicio < v.creada_en:
        return
    v.estado = "completada"
    v.sesion_id = sesion.id
    v.resultado = sesion.resultado_cierre or "omitido"
    v.completada_en = ahora_utc()
