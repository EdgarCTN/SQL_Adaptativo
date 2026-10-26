"""Consultas sobre omisiones y desafíos relacionados (R7 y R8). Solo lectura; nunca devuelven datos personales."""
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.desafios.models import Desafio, SesionDesafio
from app.modules.linea_base.models import Omision
from app.modules.motor_retiro.models import Verificacion

ORDEN_DIFICULTAD = {"D1": 1, "D2": 2, "D3": 3}
MAX_REVISADOS = 10  # cierres recientes que se recorren para contar omisiones seguidas


@dataclass(frozen=True)
class DesafioRef:
    id: int
    titulo: str
    dificultad: str
    concepto_id: int


def _ref(d: Desafio) -> DesafioRef:
    return DesafioRef(d.id, d.titulo, d.dificultad, d.concepto_id)


def contar_muy_facil(db: Session, usuario_id: int, concepto_id: int) -> int:
    """Contador de R7: omisiones «Muy fácil» del concepto (línea base + desafíos) desde la última verificación asignada."""
    cubierta = db.scalar(
        select(func.max(Verificacion.ultima_omision_id)).where(
            Verificacion.usuario_id == usuario_id, Verificacion.concepto_id == concepto_id
        )
    )
    return int(
        db.scalar(
            select(func.count())
            .select_from(Omision)
            .where(
                Omision.usuario_id == usuario_id,
                Omision.concepto_id == concepto_id,
                Omision.motivo == "muy_facil",
                Omision.id > (cubierta or 0),
            )
        )
        or 0
    )


def ultima_omision_id(db: Session, usuario_id: int, concepto_id: int) -> int:
    return int(
        db.scalar(
            select(func.max(Omision.id)).where(Omision.usuario_id == usuario_id, Omision.concepto_id == concepto_id)
        )
        or 0
    )


def hay_verificacion_pendiente(db: Session, usuario_id: int, concepto_id: int) -> bool:
    return (
        db.scalar(
            select(Verificacion.id).where(
                Verificacion.usuario_id == usuario_id,
                Verificacion.concepto_id == concepto_id,
                Verificacion.estado == "pendiente",
            )
        )
        is not None
    )


def muy_dificil_seguidas(db: Session, usuario_id: int, concepto_id: int) -> int:
    """Cuántas omisiones «Muy difícil» seguidas terminan en el cierre más reciente del concepto.

    «Seguidas» = los cierres más recientes del concepto (resueltos, abandonados u omitidos) son omisiones
    «Muy difícil» sin ningún otro cierre entre ellas.
    """
    filas = db.execute(
        select(SesionDesafio.estado, Omision.motivo)
        .join(Desafio, Desafio.id == SesionDesafio.desafio_id)
        .outerjoin(Omision, Omision.sesion_id == SesionDesafio.id)
        .where(
            SesionDesafio.usuario_id == usuario_id,
            Desafio.concepto_id == concepto_id,
            SesionDesafio.estado.in_(("resuelto", "abandonado", "omitido")),
            SesionDesafio.fin.is_not(None),
        )
        .order_by(SesionDesafio.fin.desc(), SesionDesafio.id.desc())
        .limit(MAX_REVISADOS)
    ).all()
    n = 0
    for estado, motivo in filas:
        if estado == "omitido" and motivo == "muy_dificil":
            n += 1
        else:
            break
    return n


def ids_resueltos(db: Session, usuario_id: int) -> set[int]:
    """Desafíos que el estudiante resolvió (los cerrados como NR por ver la solución completa no cuentan)."""
    return set(
        db.scalars(
            select(SesionDesafio.desafio_id).where(
                SesionDesafio.usuario_id == usuario_id,
                SesionDesafio.estado == "resuelto",
                SesionDesafio.resultado_cierre != "NR",
            )
        )
    )


def buscar_mas_basico(db: Session, usuario_id: int, desafio_id: int) -> DesafioRef | None:
    """R8: desafío activo del mismo concepto con dificultad menor que la del omitido; None si no hay.

    Prefiere uno que el estudiante no haya resuelto y, entre ellos, el más cercano en dificultad (PROVISIONAL).
    """
    omitido = db.get(Desafio, desafio_id)
    if omitido is None:
        return None
    nivel = ORDEN_DIFICULTAD.get(omitido.dificultad, 0)
    candidatos = [
        d
        for d in db.scalars(
            select(Desafio).where(
                Desafio.concepto_id == omitido.concepto_id, Desafio.activo.is_(True), Desafio.id != omitido.id
            )
        )
        if ORDEN_DIFICULTAD.get(d.dificultad, 99) < nivel
    ]
    if not candidatos:
        return None
    resueltos = ids_resueltos(db, usuario_id)
    candidatos.sort(key=lambda d: (d.id in resueltos, -ORDEN_DIFICULTAD[d.dificultad], d.id))
    return _ref(candidatos[0])
