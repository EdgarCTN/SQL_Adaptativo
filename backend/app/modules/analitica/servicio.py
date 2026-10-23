"""Interfaz pública de la capa analítica: indicadores de la ventana, serie histórica y agregados seudonimizados."""
import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.reglas import cargar_reglas
from app.modules.analitica.extractores import cierres_del_concepto, indicadores_historicos_df
from app.modules.analitica.indicadores import calcular_indicadores_df, ventana
from app.modules.analitica.models import IndicadorHistorico
from app.modules.analitica.seudonimizar import seudonimizar_df
from app.modules.linea_base.models import NivelSoporte

log = logging.getLogger("app.analitica")
CLAVES = ("n", "ta", "ni", "tr", "ua")


def indicadores_ventana(db: Session, usuario_id: int, concepto_id: int, reglas: dict | None = None) -> dict:
    """{n, ta, ni, tr, ua, desafios_desde_cambio}: ventana = últimos N cierres posteriores al último cambio de NS."""
    reglas = reglas or cargar_reglas()
    fila = db.scalar(select(NivelSoporte).where(NivelSoporte.usuario_id == usuario_id, NivelSoporte.concepto_id == concepto_id))
    df = cierres_del_concepto(db, usuario_id, concepto_id, desde=fila.ultimo_cambio_en if fila is not None else None)
    v = ventana(df, int(reglas["ventana"]["tamano"]))
    return {**calcular_indicadores_df(v), "desafios_desde_cambio": int(len(df))}


def registrar_historico(db: Session, usuario_id: int, concepto_id: int, sesion_id: int, indicadores: dict, ns: int) -> IndicadorHistorico | None:
    """Una fila por cierre (idempotente por sesión). Lanza si falla: quien llama decide cómo degradar."""
    if db.scalar(select(IndicadorHistorico.id).where(IndicadorHistorico.sesion_id == sesion_id)) is not None:
        return None
    fila = IndicadorHistorico(
        usuario_id=usuario_id, concepto_id=concepto_id, sesion_id=sesion_id, ns=int(ns),
        ta=indicadores.get("ta"), ni=indicadores.get("ni"), tr=indicadores.get("tr"), ua=indicadores.get("ua"),
        n_ventana=int(indicadores.get("n") or 0),
    )
    db.add(fila)
    db.commit()
    return fila


def _valor(x):
    if x is None or (not isinstance(x, str) and pd.isna(x)):
        return None
    if isinstance(x, pd.Timestamp):
        return x.isoformat()
    return x.item() if hasattr(x, "item") else x


def _registros(df: pd.DataFrame) -> list[dict]:
    return [{k: _valor(v) for k, v in fila.items()} for fila in df.to_dict("records")]


def serie_historica(db: Session, usuario_id: int, concepto_id: int | None = None) -> list[dict]:
    """Indicadores y NS tras cada cierre, del más antiguo al más reciente (para los gráficos de evolución)."""
    df = indicadores_historicos_df(db, usuario_id=usuario_id, concepto_id=concepto_id)
    return _registros(df[["sesion_id", "concepto_id", "concepto_codigo", "ta", "ni", "tr", "ua", "n_ventana", "ns", "creado_en"]])


def agregados(db: Session, concepto_id: int | None = None, desde: datetime | None = None, hasta: datetime | None = None) -> dict:
    """{por_concepto, por_estudiante} con el estado más reciente de cada estudiante-concepto. Solo seudónimos."""
    df = indicadores_historicos_df(db, concepto_id=concepto_id, desde=desde, hasta=hasta)
    if df.empty:
        return {"por_concepto": [], "por_estudiante": []}
    cierres = df.groupby(["usuario_id", "concepto_id"]).size().rename("cierres").reset_index()
    ultimo = df.sort_values(["creado_en", "id"]).groupby(["usuario_id", "concepto_id"]).tail(1).merge(cierres, on=["usuario_id", "concepto_id"])
    por_est = seudonimizar_df(ultimo[["usuario_id", "concepto_id", "concepto_codigo", "ns", "ta", "ni", "tr", "ua", "n_ventana", "cierres"]])
    por_concepto = []
    for (cid, codigo), g in por_est.groupby(["concepto_id", "concepto_codigo"]):
        por_concepto.append({
            "concepto_id": int(cid), "concepto_codigo": codigo, "n_estudiantes": int(g["id_pseudonimo"].nunique()),
            "n_cierres": int(g["cierres"].sum()),
            "distribucion_ns": {str(n): int((g["ns"] == n).sum()) for n in range(4)},
            "ta_media": _valor(round(g["ta"].mean(), 4)), "ni_mediana": _valor(round(g["ni"].median(), 4)),
            "tr_mediana": _valor(round(g["tr"].median(), 4)), "ua_media": _valor(round(g["ua"].mean(), 4)),
        })
    return {"por_concepto": por_concepto, "por_estudiante": _registros(por_est)}
