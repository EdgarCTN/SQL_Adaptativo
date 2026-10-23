from dataclasses import dataclass, field

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.analitica.extractores import cierres_del_concepto
from app.modules.analitica.indicadores import ventana
from app.modules.desafios.models import Concepto, Desafio, SesionDesafio
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


def _entero(x) -> int | None:
    return None if pd.isna(x) else int(x)


def construir_contexto(db: Session, sesion: SesionDesafio, desafio: Desafio, concepto: Concepto, reglas: dict) -> ContextoRegla:
    """Ventana = últimos N cierres del concepto posteriores al último cambio de NS (las omisiones no son sesiones)."""
    fila = db.scalar(
        select(NivelSoporte).where(NivelSoporte.usuario_id == sesion.usuario_id, NivelSoporte.concepto_id == concepto.id)
    )
    df = cierres_del_concepto(
        db, sesion.usuario_id, concepto.id, desde=fila.ultimo_cambio_en if fila is not None else None
    )
    recientes = ventana(df, int(reglas["ventana"]["tamano"]))
    cierres = [
        CierreReciente(
            r.resultado, int(r.intentos), _entero(r.tiempo_activo_seg), _entero(r.tiempo_referencia_seg), bool(r.uso_ayuda)
        )
        for r in recientes.itertuples()
    ]
    return ContextoRegla(
        usuario_id=sesion.usuario_id,
        concepto_id=concepto.id,
        concepto_nombre=concepto.nombre,
        ns_actual=int(fila.ns) if fila is not None else NS_POR_DEFECTO,
        sesion_id=sesion.id,
        resultado_sesion=sesion.resultado_cierre,
        cierres_recientes=cierres,
        desafios_desde_cambio=len(df),
        config=reglas,
    )
