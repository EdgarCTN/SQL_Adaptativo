"""Consultas de los reportes agregados y de la exportación (entrega 13B).

Devuelven DataFrames con `usuario_id` (se seudonimiza después). Nunca seleccionan nombre, correo ni el código SQL del
estudiante. Todas las fechas salen como datetime64[ns, UTC].
"""
from datetime import datetime

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.analitica.extractores import _df, historial_niveles_df, indicadores_historicos_df, intentos_df, sesiones_cerradas_df
from app.modules.asistencia.models import SolicitudAyuda, ValoracionAyuda
from app.modules.desafios.models import Concepto, Desafio, Intento, SesionDesafio
from app.modules.linea_base.models import LineaBaseResultado
from app.modules.motor_retiro.models import EventoMotor


def _fechas(df: pd.DataFrame, *columnas: str) -> pd.DataFrame:
    for c in columnas:
        df[c] = pd.to_datetime(df[c], utc=True)
    return df


def _rango(consulta, columna, desde: datetime | None, hasta: datetime | None):
    if desde is not None:
        consulta = consulta.where(columna >= desde)
    if hasta is not None:
        consulta = consulta.where(columna <= hasta)
    return consulta


def conceptos(db: Session) -> list[dict]:
    """Conceptos en su orden natural (por id): {id, codigo, nombre}."""
    filas = db.execute(select(Concepto.id, Concepto.codigo, Concepto.nombre).order_by(Concepto.id)).all()
    return [{"id": i, "codigo": c, "nombre": n} for i, c, n in filas]


def sesiones_periodo_df(db: Session, desde: datetime | None, hasta: datetime | None) -> pd.DataFrame:
    """Sesiones iniciadas en el periodo (sin las omitidas, que no son actividad con el desafío)."""
    consulta = (
        select(
            SesionDesafio.id, SesionDesafio.usuario_id, Concepto.codigo, Desafio.dificultad, SesionDesafio.inicio,
            SesionDesafio.estado,
        )
        .join(Desafio, Desafio.id == SesionDesafio.desafio_id)
        .join(Concepto, Concepto.id == Desafio.concepto_id)
        .where(SesionDesafio.estado != "omitido")
        .order_by(SesionDesafio.inicio, SesionDesafio.id)
    )
    df = _df(
        db.execute(_rango(consulta, SesionDesafio.inicio, desde, hasta)).all(),
        ["sesion_id", "usuario_id", "concepto_codigo", "dificultad", "inicio", "estado"],
    )
    return _fechas(df, "inicio")


def intentos_por_sesion(db: Session, sesion_ids: list[int]) -> pd.Series:
    """Número de envíos de cada sesión (índice = sesion_id)."""
    return intentos_df(db, sesion_ids).groupby("sesion_id").size()


def cierres_df(db: Session, hasta: datetime | None) -> pd.DataFrame:
    """Desafíos cerrados (resuelto o abandonado) hasta `hasta`, del más antiguo al más reciente.

    Columnas: sesion_id, usuario_id, concepto_id, concepto_codigo, dificultad, fin, resultado, intentos, tr.
    `tr` = tiempo activo ÷ tiempo de referencia del desafío (None si no se midió).
    """
    df = sesiones_cerradas_df(db)
    cols = ["sesion_id", "usuario_id", "concepto_id", "concepto_codigo", "dificultad", "fin", "resultado", "intentos", "tr"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    codigos = {c["id"]: c["codigo"] for c in conceptos(db)}
    df["concepto_codigo"] = df["concepto_id"].map(codigos)
    df["intentos"] = df["sesion_id"].map(intentos_por_sesion(db, [int(i) for i in df["sesion_id"]])).fillna(0).astype(int)
    referencia = df["tiempo_referencia_seg"].where(df["tiempo_referencia_seg"] > 0)
    df["tr"] = df["tiempo_activo_seg"] / referencia
    df = _fechas(df, "fin")
    if hasta is not None:
        df = df[df["fin"] <= pd.Timestamp(hasta)]
    return df.sort_values(["fin", "sesion_id"]).reset_index(drop=True)[cols]


def ayudas_periodo_df(db: Session, desde: datetime | None, hasta: datetime | None) -> pd.DataFrame:
    """Una fila por ayuda entregada en el periodo, con su valoración (1, -1 o vacío). Sin el texto ni la consulta."""
    consulta = (
        select(
            SolicitudAyuda.id, SolicitudAyuda.usuario_id, SolicitudAyuda.sesion_id, Concepto.codigo, Desafio.dificultad,
            SolicitudAyuda.tipo_ayuda, SolicitudAyuda.tipo_solicitado, SolicitudAyuda.intentos_previos,
            func.coalesce(SolicitudAyuda.mostrada_sola, False), func.coalesce(SolicitudAyuda.fue_respaldo, False),
            SolicitudAyuda.proveedor, SolicitudAyuda.momento, ValoracionAyuda.valor,
        )
        .join(Desafio, Desafio.id == SolicitudAyuda.desafio_id)
        .join(Concepto, Concepto.id == Desafio.concepto_id)
        .outerjoin(ValoracionAyuda, ValoracionAyuda.solicitud_id == SolicitudAyuda.id)
        .order_by(SolicitudAyuda.momento, SolicitudAyuda.id)
    )
    df = _df(
        db.execute(_rango(consulta, SolicitudAyuda.momento, desde, hasta)).all(),
        ["solicitud_id", "usuario_id", "sesion_id", "concepto_codigo", "dificultad", "tipo_ayuda", "tipo_solicitado",
         "intentos_previos", "mostrada_sola", "fue_respaldo", "proveedor", "momento", "valoracion"],
        ("intentos_previos", "valoracion"),
    )
    df["mostrada_sola"] = df["mostrada_sola"].astype(bool)
    df["fue_respaldo"] = df["fue_respaldo"].astype(bool)
    return _fechas(df, "momento")


def intentos_periodo_df(db: Session, desde: datetime | None, hasta: datetime | None) -> pd.DataFrame:
    """Un renglón por envío hecho en el periodo. Sin el código del estudiante ni la salida de su consulta."""
    consulta = (
        select(
            Intento.sesion_id, SesionDesafio.usuario_id, Concepto.codigo, Desafio.dificultad, Intento.numero,
            Intento.correcto, Intento.creado_en,
        )
        .join(SesionDesafio, SesionDesafio.id == Intento.sesion_id)
        .join(Desafio, Desafio.id == SesionDesafio.desafio_id)
        .join(Concepto, Concepto.id == Desafio.concepto_id)
        .order_by(Intento.creado_en, Intento.id)
    )
    df = _df(
        db.execute(_rango(consulta, Intento.creado_en, desde, hasta)).all(),
        ["sesion_id", "usuario_id", "concepto_codigo", "dificultad", "numero", "correcto", "creado_en"],
    )
    return _fechas(df, "creado_en")


def historial_niveles_hasta_df(db: Session, hasta: datetime | None) -> pd.DataFrame:
    """Todos los cambios de NS hasta `hasta` (la lógica de los indicadores necesita la historia completa)."""
    df = historial_niveles_df(db, hasta=hasta)
    codigos = {c["id"]: c["codigo"] for c in conceptos(db)}
    df["concepto_codigo"] = df["concepto_id"].map(codigos)
    return _fechas(df, "creado_en")


def indicadores_periodo_df(db: Session, desde: datetime | None, hasta: datetime | None) -> pd.DataFrame:
    df = indicadores_historicos_df(db, desde=desde, hasta=hasta)
    return _fechas(df, "creado_en")


def activaciones_df(db: Session, reglas: tuple[str, ...], desde: datetime | None, hasta: datetime | None) -> pd.DataFrame:
    """Activaciones de reglas que no cambian el NS (R9, R10…), registradas en `eventos_motor`."""
    consulta = (
        select(EventoMotor.usuario_id, EventoMotor.concepto_id, EventoMotor.sesion_id, EventoMotor.regla, EventoMotor.creado_en)
        .where(EventoMotor.regla.in_(reglas), EventoMotor.usuario_id.is_not(None))
        .order_by(EventoMotor.creado_en, EventoMotor.id)
    )
    df = _df(
        db.execute(_rango(consulta, EventoMotor.creado_en, desde, hasta)).all(),
        ["usuario_id", "concepto_id", "sesion_id", "regla", "creado_en"],
    )
    return _fechas(df, "creado_en")


def linea_base_periodo(db: Session, desde: datetime | None, hasta: datetime | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(m global por estudiante, m por estudiante y concepto) de las líneas base hechas en el periodo."""
    consulta = select(
        LineaBaseResultado.usuario_id, LineaBaseResultado.m_global, LineaBaseResultado.m_por_concepto
    ).order_by(LineaBaseResultado.creado_en, LineaBaseResultado.id)
    filas = db.execute(_rango(consulta, LineaBaseResultado.creado_en, desde, hasta)).all()
    globales, por_concepto = [], []
    for usuario_id, m_global, m_conceptos in filas:
        globales.append((usuario_id, m_global))
        for codigo, detalle in (m_conceptos or {}).items():
            m = detalle.get("m") if isinstance(detalle, dict) else detalle
            por_concepto.append((usuario_id, codigo, m))
    g = _df(globales, ["usuario_id", "m_global"], ("m_global",))
    c = _df(por_concepto, ["usuario_id", "concepto_codigo", "m"], ("m",))
    return g, c
