"""Exportación seudonimizada para el análisis de la tesis (RNF-23).

Cuatro tablas por estudiante-seudónimo: intentos, ayudas, cambios de NS e indicadores. Ninguna lleva nombre, correo,
el código SQL del estudiante ni textos libres; `id_pseudonimo` es el HMAC del id con ANON_SALT. Lo usan el endpoint
`GET /reportes/exportar` y `scripts/exportar_tesis.py`, así que ambos dan lo mismo.
"""
import io
import zipfile
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from app.modules.analitica import extractores_reportes as ext
from app.modules.analitica.seudonimizar import COLUMNAS_PERSONALES, seudonimizar_df

TIPOS = ("intentos", "ayudas", "cambios_ns", "indicadores")
COLUMNAS = {
    "intentos": ["id_pseudonimo", "sesion_id", "concepto_codigo", "dificultad", "numero", "correcto", "creado_en"],
    "ayudas": [
        "id_pseudonimo", "sesion_id", "concepto_codigo", "dificultad", "tipo_ayuda", "tipo_solicitado", "intentos_previos",
        "mostrada_sola", "fue_respaldo", "proveedor", "valoracion", "momento",
    ],
    "cambios_ns": ["id_pseudonimo", "concepto_codigo", "ns_anterior", "ns_nuevo", "regla", "creado_en"],
    "indicadores": ["id_pseudonimo", "sesion_id", "concepto_codigo", "ta", "ni", "tr", "ua", "n_ventana", "ns", "creado_en"],
}


def _tabla_cruda(db: Session, tipo: str, desde: datetime | None, hasta: datetime | None) -> pd.DataFrame:
    if tipo == "intentos":
        return ext.intentos_periodo_df(db, desde, hasta)
    if tipo == "ayudas":
        return ext.ayudas_periodo_df(db, desde, hasta)
    if tipo == "cambios_ns":
        h = ext.historial_niveles_hasta_df(db, hasta)
        return h[h["creado_en"] >= pd.Timestamp(desde)] if desde is not None else h
    if tipo == "indicadores":
        return ext.indicadores_periodo_df(db, desde, hasta)
    raise ValueError(f"Tipo de exportación desconocido: {tipo}")


def verificar_sin_datos_personales(df: pd.DataFrame) -> None:
    """Defensa en profundidad: si una columna personal o un correo se colara, la exportación se detiene."""
    if COLUMNAS_PERSONALES & set(df.columns) or "usuario_id" in df.columns:
        raise ValueError("La exportación contiene columnas personales.")
    for c in df.columns:
        if df[c].map(lambda v: isinstance(v, str) and "@" in v).any():
            raise ValueError("La exportación contiene un correo.")


def tabla(db: Session, tipo: str, desde: datetime | None = None, hasta: datetime | None = None) -> pd.DataFrame:
    """Tabla seudonimizada lista para guardar: columnas fijas, fechas ISO 8601 (UTC) y orden cronológico."""
    df = seudonimizar_df(_tabla_cruda(db, tipo, desde, hasta))
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            df[c] = df[c].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    df = df.reindex(columns=COLUMNAS[tipo])
    verificar_sin_datos_personales(df)
    return df


def a_csv(df: pd.DataFrame) -> str:
    return df.to_csv(index=False, lineterminator="\r\n")


def nombre_archivo(tipo: str, desde: datetime | None, hasta: datetime | None) -> str:
    d = desde.strftime("%Y%m%d") if desde else "inicio"
    h = hasta.strftime("%Y%m%d") if hasta else "hoy"
    return f"{tipo}_{d}_{h}.csv"


def todas_en_zip(db: Session, desde: datetime | None = None, hasta: datetime | None = None) -> tuple[bytes, dict[str, int]]:
    """Las cuatro tablas en un ZIP (un CSV por tabla) y cuántas filas tiene cada una."""
    memoria = io.BytesIO()
    filas: dict[str, int] = {}
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as z:
        for tipo in TIPOS:
            df = tabla(db, tipo, desde, hasta)
            filas[tipo] = len(df)
            z.writestr(nombre_archivo(tipo, desde, hasta), a_csv(df))
    return memoria.getvalue(), filas
