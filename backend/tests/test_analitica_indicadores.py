import random
from statistics import median

import pandas as pd
import pytest

from app.modules.analitica.indicadores import (
    calcular_indicadores_df, calcular_ni, calcular_ta, calcular_tr, calcular_ua, sesiones_con_uso_ayuda, ventana,
)
from app.modules.motor_retiro.evaluador import evaluar
from app.modules.motor_retiro.indicadores import CierreReciente, calcular_indicadores
from test_motor_reglas import CASOS, ctx


def _legado(cierres):
    """Implementación anterior (Python puro) usada como oráculo de equivalencia."""
    if not cierres:
        return (0, None, None, None)
    ta = sum(1 for c in cierres if c.resultado in ("SA", "CP")) / len(cierres)
    ni = float(median(c.intentos for c in cierres))
    razones = [c.tiempo_activo_seg / c.tiempo_referencia_seg for c in cierres if c.tiempo_activo_seg is not None and c.tiempo_referencia_seg]
    tr = float(median(razones)) if razones else None
    return (len(cierres), round(ta, 6), round(ni, 6), None if tr is None else round(tr, 6))


def _tupla(ind):
    return (ind.n, ind.ta, ind.ni, ind.tr)


@pytest.mark.parametrize("nombre,ns,cierres,desde,regla,ns_esperado", CASOS, ids=[x[0] for x in CASOS])
def test_equivalencia_con_los_casos_actuales_de_r1_r4_r5(nombre, ns, cierres, desde, regla, ns_esperado):
    assert _tupla(calcular_indicadores(cierres)) == _legado(cierres)
    ev = evaluar(ctx(ns, cierres, desde))
    assert (ev.regla, ev.ns_nuevo) == (regla, ns_esperado)


def test_equivalencia_aleatoria_con_la_implementacion_anterior():
    azar = random.Random(7)
    for _ in range(300):
        cierres = [
            CierreReciente(
                azar.choice(["SA", "CP", "CE", "NR"]), azar.randint(0, 8),
                azar.choice([None, azar.randint(0, 900)]), azar.choice([None, 120, 240, 360]),
            )
            for _ in range(azar.randint(0, 5))
        ]
        assert _tupla(calcular_indicadores(cierres)) == _legado(cierres)


def _v(filas):
    return pd.DataFrame(filas, columns=["resultado", "intentos", "tiempo_activo_seg", "tiempo_referencia_seg", "uso_ayuda"])


def test_ta_ni_tr_con_dataframe_sintetico():
    v = _v([("SA", 1, 60, 120, False), ("CP", 2, 120, 120, True), ("CE", 5, 300, 120, True), ("NR", 3, 120, 120, True), ("SA", 1, 120, 120, False)])
    assert calcular_ta(v) == 0.6 and calcular_ni(v) == 2.0 and calcular_tr(v) == 1.0
    assert calcular_indicadores_df(v) == {"n": 5, "ta": 0.6, "ni": 2.0, "tr": 1.0, "ua": 0.6}


def test_ventana_vacia_y_sin_tiempo_medido():
    vacia = _v([])
    assert calcular_indicadores_df(vacia) == {"n": 0, "ta": None, "ni": None, "tr": None, "ua": None}
    sin_tiempo = _v([("SA", 1, None, 120, False), ("SA", 1, 50, None, False), ("SA", 1, 50, 0, False)])
    assert calcular_tr(sin_tiempo) is None


def test_ua_cuenta_pedir_o_aceptar_y_no_la_ayuda_mostrada_sola():
    ayudas = pd.DataFrame(
        {"sesion_id": [1, 1, 2, 3], "tipo_ayuda": ["AY1", "AY2", "AY1", "AY1"], "mostrada_sola": [False, False, True, False]}
    )
    assert sesiones_con_uso_ayuda(ayudas) == {1, 3}  # la 2 solo vio ayuda mostrada sola; la 4 no tuvo ayudas
    assert sesiones_con_uso_ayuda(pd.DataFrame(columns=["sesion_id", "mostrada_sola"])) == set()
    v = _v([("CP", 2, 60, 120, True), ("SA", 1, 60, 120, False), ("SA", 1, 60, 120, False), ("CE", 3, 60, 120, True)])
    assert calcular_ua(v) == 0.5
    assert calcular_ua(_v([("SA", 1, 60, 120, False)])) == 0.0


def test_calcular_indicadores_incluye_ua_y_por_defecto_es_cero():
    cierres = [CierreReciente("CP", 2, 60, 120, True), CierreReciente("SA", 1, 60, 120)]
    ind = calcular_indicadores(cierres)
    assert ind.ua == 0.5 and ind.como_dict() == {"n": 2, "ta": 1.0, "ni": 1.5, "tr": 0.5, "ua": 0.5}


def test_ventana_toma_los_ultimos_n_en_orden_cronologico():
    df = pd.DataFrame({"sesion_id": [7, 6, 5, 4, 3, 2, 1]})  # más reciente primero
    assert ventana(df, 5)["sesion_id"].tolist() == [3, 4, 5, 6, 7]
