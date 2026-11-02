"""Indicadores de la ventana (Matriz, sección 1) sobre DataFrames. Funciones puras: no tocan la base de datos.

Columnas que espera una ventana: resultado (SA|CP|CE|NR), intentos, tiempo_activo_seg, tiempo_referencia_seg, uso_ayuda.
- TA = éxitos (SA o CP) ÷ desafíos · NI = mediana de envíos (en un NR, los hechos)
- TR = mediana de tiempo activo ÷ tiempo de referencia (se ignoran desafíos sin tiempo medido)
- UA = proporción de desafíos donde pidió o aceptó ayuda; la ayuda mostrada sola NO cuenta.
"""
import pandas as pd

EXITOS = ("SA", "CP")
DECIMALES = 6


def sesiones_con_uso_ayuda(ayudas: pd.DataFrame) -> set[int]:
    """Sesiones con al menos una ayuda pedida o aceptada. Columnas: sesion_id y (opcional) mostrada_sola.

    `mostrada_sola` es la marca de cada solicitud (solicitudes_ayuda.mostrada_sola, entrega 8): una sesión con una ayuda
    mostrada sola y otra pedida cuenta como uso de ayuda por la pedida.
    """
    if ayudas is None or ayudas.empty:
        return set()
    if "mostrada_sola" in ayudas.columns:
        ayudas = ayudas[~ayudas["mostrada_sola"].astype(bool)]
    return {int(s) for s in ayudas["sesion_id"].unique()}


def ventana(cierres_recientes_primero: pd.DataFrame, tamano: int) -> pd.DataFrame:
    """Los últimos `tamano` cierres, del más antiguo al más reciente (la entrada viene del más reciente al más antiguo)."""
    return cierres_recientes_primero.head(int(tamano)).iloc[::-1]


def _redondear(x) -> float | None:
    return None if x is None or pd.isna(x) else round(float(x), DECIMALES)


def calcular_ta(v: pd.DataFrame) -> float | None:
    return None if v.empty else _redondear(v["resultado"].isin(EXITOS).astype(float).mean())


def calcular_ni(v: pd.DataFrame) -> float | None:
    return None if v.empty else _redondear(pd.to_numeric(v["intentos"], errors="coerce").median())


def calcular_tr(v: pd.DataFrame) -> float | None:
    if v.empty:
        return None
    activo = pd.to_numeric(v["tiempo_activo_seg"], errors="coerce")
    ref = pd.to_numeric(v["tiempo_referencia_seg"], errors="coerce")
    ref = ref.where(ref.notna() & (ref != 0))
    razones = (activo / ref).dropna()
    return None if razones.empty else _redondear(razones.median())


def calcular_ua(v: pd.DataFrame) -> float | None:
    if v.empty:
        return None
    if "uso_ayuda" not in v.columns:
        return 0.0
    return _redondear(v["uso_ayuda"].fillna(False).astype(bool).astype(float).mean())


def proporcion_pedidos_directos(pedidos: pd.DataFrame, tipos: tuple[str, ...], intentos_max: int) -> float | None:
    """R9: proporción de pedidos de ayuda que son de alguno de `tipos` (AY3 o AY4) con `intentos_max` envíos o menos
    antes. Se usa el tipo SOLICITADO (el que correspondía antes de aplicar los mínimos de fallos), porque con los mínimos
    la ayuda entregada nunca sería AY3 o AY4 con tan pocos intentos. Columnas: tipo_solicitado (o tipo_ayuda si falta),
    intentos_previos. None si no hubo pedidos (las ayudas mostradas solas no deben venir aquí)."""
    if pedidos is None or pedidos.empty:
        return None
    tipo = pedidos["tipo_solicitado"].where(pedidos["tipo_solicitado"].notna(), pedidos["tipo_ayuda"])
    previos = pd.to_numeric(pedidos["intentos_previos"], errors="coerce")
    directo = tipo.isin(tipos) & previos.notna() & (previos <= int(intentos_max))
    return _redondear(directo.astype(float).mean())


def calcular_indicadores_df(v: pd.DataFrame) -> dict:
    """{n, ta, ni, tr, ua}; todo None (salvo n=0) si la ventana está vacía."""
    return {"n": int(len(v)), "ta": calcular_ta(v), "ni": calcular_ni(v), "tr": calcular_tr(v), "ua": calcular_ua(v)}
