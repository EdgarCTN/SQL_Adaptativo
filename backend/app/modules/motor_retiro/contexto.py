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
from app.modules.motor_retiro.omisiones import contar_muy_facil, hay_verificacion_pendiente, muy_dificil_seguidas


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
    # Omisiones (R7, R8). Solo se llenan cuando el cierre que dispara el motor es una omisión.
    omision_motivo: str | None = None  # muy_facil | muy_dificil si la sesión que se acaba de cerrar fue omitida
    omisiones_muy_facil: int = 0  # contador de R7: línea base + desafíos, desde la última verificación asignada
    omisiones_muy_dificil_seguidas: int = 0  # omisiones «Muy difícil» seguidas que terminan en la actual (incluida)
    verificacion_pendiente: bool = False  # ya hay una verificación sin completar en el concepto
    indicadores: Indicadores = field(init=False)

    def __post_init__(self) -> None:
        self.indicadores = calcular_indicadores(self.cierres_recientes)


def _entero(x) -> int | None:
    return None if pd.isna(x) else int(x)


def construir_contexto(
    db: Session, sesion: SesionDesafio, desafio: Desafio, concepto: Concepto, reglas: dict, omision_motivo: str | None = None
) -> ContextoRegla:
    """Ventana = últimos N cierres del concepto posteriores al último cambio de NS (las sesiones omitidas no entran:
    `sesiones_cerradas_df` solo toma resueltas y abandonadas). `omision_motivo` indica que el cierre fue una omisión."""
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
        omision_motivo=omision_motivo,
        omisiones_muy_facil=contar_muy_facil(db, sesion.usuario_id, concepto.id) if omision_motivo == "muy_facil" else 0,
        omisiones_muy_dificil_seguidas=(
            muy_dificil_seguidas(db, sesion.usuario_id, concepto.id) if omision_motivo == "muy_dificil" else 0
        ),
        verificacion_pendiente=(
            hay_verificacion_pendiente(db, sesion.usuario_id, concepto.id) if omision_motivo == "muy_facil" else False
        ),
    )
