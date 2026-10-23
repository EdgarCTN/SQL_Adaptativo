"""Consultas a DataFrames (sesiones, intentos, ayudas, historiales). Nunca seleccionan nombre ni correo."""
from datetime import datetime

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.analitica.indicadores import sesiones_con_uso_ayuda
from app.modules.analitica.models import IndicadorHistorico
from app.modules.asistencia.models import SolicitudAyuda
from app.modules.desafios.models import Concepto, Desafio, Intento, SesionDesafio
from app.modules.motor_retiro.models import HistorialNivel

TROZO = 500  # tamaño de los IN (...) para no pasar el límite de variables de SQLite


def _df(filas, columnas: list[str], numericas: tuple[str, ...] = ()) -> pd.DataFrame:
    df = pd.DataFrame([tuple(f) for f in filas], columns=columnas)
    for c in numericas:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _por_trozos(db: Session, ids: list[int], construir) -> list:
    filas: list = []
    for i in range(0, len(ids), TROZO):
        filas.extend(db.execute(construir(ids[i : i + TROZO])).all())
    return filas


def sesiones_cerradas_df(
    db: Session, usuario_id: int | None = None, concepto_id: int | None = None, desde: datetime | None = None
) -> pd.DataFrame:
    """Sesiones resueltas o abandonadas con resultado, del cierre más reciente al más antiguo. `desde`: fin > desde."""
    consulta = (
        select(
            SesionDesafio.id, SesionDesafio.usuario_id, Desafio.concepto_id, SesionDesafio.desafio_id, Desafio.dificultad,
            SesionDesafio.inicio, SesionDesafio.fin, SesionDesafio.resultado_cierre, SesionDesafio.tiempo_activo_seg,
            Desafio.tiempo_referencia_seg,
        )
        .join(Desafio, Desafio.id == SesionDesafio.desafio_id)
        .where(
            SesionDesafio.estado.in_(("resuelto", "abandonado")),
            SesionDesafio.fin.is_not(None),
            SesionDesafio.resultado_cierre.is_not(None),
        )
        .order_by(SesionDesafio.fin.desc(), SesionDesafio.id.desc())
    )
    if usuario_id is not None:
        consulta = consulta.where(SesionDesafio.usuario_id == usuario_id)
    if concepto_id is not None:
        consulta = consulta.where(Desafio.concepto_id == concepto_id)
    if desde is not None:
        consulta = consulta.where(SesionDesafio.fin > desde)
    return _df(
        db.execute(consulta).all(),
        ["sesion_id", "usuario_id", "concepto_id", "desafio_id", "dificultad", "inicio", "fin", "resultado",
         "tiempo_activo_seg", "tiempo_referencia_seg"],
        ("tiempo_activo_seg", "tiempo_referencia_seg"),
    )


def intentos_df(db: Session, sesion_ids: list[int]) -> pd.DataFrame:
    """Un renglón por envío (sin el código del estudiante)."""
    filas = _por_trozos(
        db,
        sesion_ids,
        lambda t: select(Intento.sesion_id, Intento.numero, Intento.correcto, Intento.creado_en).where(Intento.sesion_id.in_(t)),
    )
    return _df(filas, ["sesion_id", "numero", "correcto", "creado_en"])


def ayudas_df(db: Session, sesion_ids: list[int]) -> pd.DataFrame:
    """Un renglón por ayuda entregada; `mostrada_sola` es la marca de la sesión."""
    filas = _por_trozos(
        db,
        sesion_ids,
        lambda t: select(
            SolicitudAyuda.sesion_id, SolicitudAyuda.tipo_ayuda, SolicitudAyuda.momento, SolicitudAyuda.fue_respaldo,
            func.coalesce(SesionDesafio.ayuda_mostrada_sola, False),
        )
        .join(SesionDesafio, SesionDesafio.id == SolicitudAyuda.sesion_id)
        .where(SolicitudAyuda.sesion_id.in_(t)),
    )
    df = _df(filas, ["sesion_id", "tipo_ayuda", "momento", "fue_respaldo", "mostrada_sola"])
    df["mostrada_sola"] = df["mostrada_sola"].astype(bool)
    return df


def historial_niveles_df(db: Session, usuario_id: int | None = None, concepto_id: int | None = None) -> pd.DataFrame:
    consulta = select(
        HistorialNivel.usuario_id, HistorialNivel.concepto_id, HistorialNivel.ns_anterior, HistorialNivel.ns_nuevo,
        HistorialNivel.regla, HistorialNivel.creado_en,
    ).order_by(HistorialNivel.creado_en, HistorialNivel.id)
    if usuario_id is not None:
        consulta = consulta.where(HistorialNivel.usuario_id == usuario_id)
    if concepto_id is not None:
        consulta = consulta.where(HistorialNivel.concepto_id == concepto_id)
    return _df(db.execute(consulta).all(), ["usuario_id", "concepto_id", "ns_anterior", "ns_nuevo", "regla", "creado_en"])


def indicadores_historicos_df(
    db: Session, usuario_id: int | None = None, concepto_id: int | None = None,
    desde: datetime | None = None, hasta: datetime | None = None,
) -> pd.DataFrame:
    consulta = (
        select(
            IndicadorHistorico.id, IndicadorHistorico.usuario_id, IndicadorHistorico.concepto_id, Concepto.codigo,
            IndicadorHistorico.sesion_id, IndicadorHistorico.ta, IndicadorHistorico.ni, IndicadorHistorico.tr,
            IndicadorHistorico.ua, IndicadorHistorico.n_ventana, IndicadorHistorico.ns, IndicadorHistorico.creado_en,
        )
        .join(Concepto, Concepto.id == IndicadorHistorico.concepto_id)
        .order_by(IndicadorHistorico.creado_en, IndicadorHistorico.id)
    )
    if usuario_id is not None:
        consulta = consulta.where(IndicadorHistorico.usuario_id == usuario_id)
    if concepto_id is not None:
        consulta = consulta.where(IndicadorHistorico.concepto_id == concepto_id)
    if desde is not None:
        consulta = consulta.where(IndicadorHistorico.creado_en >= desde)
    if hasta is not None:
        consulta = consulta.where(IndicadorHistorico.creado_en <= hasta)
    return _df(
        db.execute(consulta).all(),
        ["id", "usuario_id", "concepto_id", "concepto_codigo", "sesion_id", "ta", "ni", "tr", "ua", "n_ventana", "ns", "creado_en"],
        ("ta", "ni", "tr", "ua"),
    )


def cierres_del_concepto(db: Session, usuario_id: int, concepto_id: int, desde: datetime | None = None) -> pd.DataFrame:
    """Cierres del concepto (más reciente primero) con `intentos` y `uso_ayuda`. `desde` = último cambio de NS."""
    df = sesiones_cerradas_df(db, usuario_id, concepto_id, desde)
    ids = [int(i) for i in df["sesion_id"]]
    conteo = intentos_df(db, ids).groupby("sesion_id").size()
    df["intentos"] = df["sesion_id"].map(conteo).fillna(0).astype(int)
    df["uso_ayuda"] = df["sesion_id"].isin(sesiones_con_uso_ayuda(ayudas_df(db, ids)))
    return df
