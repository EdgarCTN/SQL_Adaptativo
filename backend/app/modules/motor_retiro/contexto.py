from dataclasses import dataclass, field

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.desafios.models import Concepto, Desafio, Intento, SesionDesafio
from app.modules.linea_base.models import NivelSoporte
from app.modules.motor_retiro.indicadores import CierreReciente, Indicadores, calcular_indicadores
from app.modules.motor_retiro.niveles import NS_POR_DEFECTO


@dataclass
class ContextoRegla:
    """Todo lo que una regla necesita para decidir (sin acceso a la base de datos)."""

    usuario_id: int
    concepto_id: int
    concepto_nombre: str
    ns_actual: int
    sesion_id: int | None
    resultado_sesion: str | None  # SA | CP | CE | NR de la sesión que se acaba de cerrar
    cierres_recientes: list[CierreReciente]  # la ventana: del más antiguo al más reciente
    desafios_desde_cambio: int  # todos los cerrados desde el último cambio de NS (puede superar la ventana)
    config: dict  # reglas.json
    indicadores: Indicadores = field(init=False)

    def __post_init__(self) -> None:
        self.indicadores = calcular_indicadores(self.cierres_recientes)


def construir_contexto(db: Session, sesion: SesionDesafio, desafio: Desafio, concepto: Concepto, reglas: dict) -> ContextoRegla:
    """Ventana = últimos N cierres del concepto posteriores al último cambio de NS (las omisiones no son sesiones)."""
    fila = db.scalar(
        select(NivelSoporte).where(NivelSoporte.usuario_id == sesion.usuario_id, NivelSoporte.concepto_id == concepto.id)
    )
    consulta = (
        select(SesionDesafio, Desafio.tiempo_referencia_seg)
        .join(Desafio, Desafio.id == SesionDesafio.desafio_id)
        .where(
            SesionDesafio.usuario_id == sesion.usuario_id,
            Desafio.concepto_id == concepto.id,
            SesionDesafio.estado.in_(("resuelto", "abandonado")),
            SesionDesafio.fin.is_not(None),
            SesionDesafio.resultado_cierre.is_not(None),
        )
        .order_by(SesionDesafio.fin.desc(), SesionDesafio.id.desc())
    )
    if fila is not None and fila.ultimo_cambio_en is not None:
        consulta = consulta.where(SesionDesafio.fin > fila.ultimo_cambio_en)
    filas = db.execute(consulta).all()
    recientes = filas[: int(reglas["ventana"]["tamano"])][::-1]
    ids = [s.id for s, _ in recientes]
    intentos = dict(
        db.execute(select(Intento.sesion_id, func.count()).where(Intento.sesion_id.in_(ids)).group_by(Intento.sesion_id)).all()
    ) if ids else {}
    cierres = [
        CierreReciente(s.resultado_cierre, int(intentos.get(s.id, 0)), s.tiempo_activo_seg, ref) for s, ref in recientes
    ]
    return ContextoRegla(
        usuario_id=sesion.usuario_id,
        concepto_id=concepto.id,
        concepto_nombre=concepto.nombre,
        ns_actual=int(fila.ns) if fila is not None else NS_POR_DEFECTO,
        sesion_id=sesion.id,
        resultado_sesion=sesion.resultado_cierre,
        cierres_recientes=cierres,
        desafios_desde_cambio=len(filas),
        config=reglas,
    )
