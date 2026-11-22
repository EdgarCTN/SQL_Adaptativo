"""Reportes agregados de uso, desempeño y eficacia del retiro (RF-30, RNF-23).

Cálculo puro sobre DataFrames: no toca la base de datos ni conoce nombres o correos. Cada tabla es un grupo de
estudiantes; si un grupo tiene entre 1 y `n_minimo - 1` estudiantes sus cifras no se muestran (`suprimido: True`).
No se publican totales que sumen los grupos, para que una celda suprimida no se pueda recuperar por resta.
"""
from datetime import datetime

import pandas as pd

TIPOS_CAMBIO = ("retiro", "refuerzo", "recaida", "otro")
TIPOS_AYUDA = ("AY1", "AY2", "AY3", "AY4")


def pequeno(n: int, n_minimo: int) -> bool:
    """Grupo que no se puede mostrar: tiene estudiantes, pero menos que el mínimo. Un grupo vacío (0) sí se muestra."""
    return 0 < n < n_minimo


def _r(x, decimales: int = 4):
    return None if x is None or pd.isna(x) else round(float(x), decimales)


def en_periodo(serie: pd.Series, desde: datetime | None, hasta: datetime | None) -> pd.Series:
    ok = pd.Series(True, index=serie.index)
    if desde is not None:
        ok &= serie >= pd.Timestamp(desde)
    if hasta is not None:
        ok &= serie <= pd.Timestamp(hasta)
    return ok


def _orden(conceptos: list[dict]) -> dict[str, int]:
    return {c["codigo"]: i for i, c in enumerate(conceptos)}


def _fila(base: dict, campos: tuple[str, ...], valores: dict | None) -> dict:
    """Fila de reporte: con `valores` cuando se puede mostrar; con todo en None y `suprimido` cuando no."""
    if valores is None:
        return {**base, **{k: None for k in campos}, "suprimido": True}
    return {**base, **{k: valores.get(k) for k in campos}, "suprimido": False}


# ---------------------------------------------------------------- uso
def uso_semanal(sesiones: pd.DataFrame, envios_por_sesion: pd.Series, n_minimo: int) -> list[dict]:
    """Estudiantes activos, sesiones y envíos por semana (lunes, UTC) de inicio de la sesión."""
    campos = ("estudiantes_activos", "sesiones", "intentos")
    if sesiones.empty:
        return []
    d = sesiones.copy()
    sin_zona = d["inicio"].dt.tz_convert("UTC").dt.tz_localize(None)
    d["semana"] = sin_zona.dt.to_period("W-SUN").dt.start_time.dt.strftime("%Y-%m-%d")
    d["intentos"] = d["sesion_id"].map(envios_por_sesion).fillna(0)
    filas = []
    for semana, g in d.groupby("semana"):
        n = int(g["usuario_id"].nunique())
        valores = None if pequeno(n, n_minimo) else {
            "estudiantes_activos": n, "sesiones": int(len(g)), "intentos": int(g["intentos"].sum()),
        }
        filas.append(_fila({"semana": semana}, campos, valores))
    return filas


# ---------------------------------------------------------------- desempeño
def desempeno(cierres: pd.DataFrame, conceptos: list[dict], n_minimo: int) -> list[dict]:
    """Tasas SA, CP, CE y NR, envíos medios y TR mediano por concepto y dificultad."""
    campos = ("n_estudiantes", "n_desafios", "tasa_sa", "tasa_cp", "tasa_ce", "tasa_nr", "intentos_medios", "tr_mediana")
    if cierres.empty:
        return []
    orden = _orden(conceptos)
    filas = []
    for (codigo, dificultad), g in cierres.groupby(["concepto_codigo", "dificultad"]):
        n = int(g["usuario_id"].nunique())
        valores = None
        if not pequeno(n, n_minimo):
            tasa = lambda r: _r((g["resultado"] == r).mean())  # noqa: E731
            valores = {
                "n_estudiantes": n, "n_desafios": int(len(g)), "tasa_sa": tasa("SA"), "tasa_cp": tasa("CP"),
                "tasa_ce": tasa("CE"), "tasa_nr": tasa("NR"), "intentos_medios": _r(g["intentos"].mean()),
                "tr_mediana": _r(g["tr"].median()),
            }
        filas.append(_fila({"concepto": codigo, "dificultad": dificultad}, campos, valores))
    return sorted(filas, key=lambda f: (orden.get(f["concepto"], 99), f["dificultad"]))


# ---------------------------------------------------------------- NS por concepto (sobre analitica.agregados)
def distribucion_ns(por_concepto: list[dict], conceptos: list[dict], n_minimo: int) -> list[dict]:
    """Distribución del NS más reciente de cada estudiante en cada concepto. `por_concepto` viene de `agregados`."""
    campos = ("n_estudiantes", "ns0", "ns1", "ns2", "ns3", "ta_media", "ni_mediana", "tr_mediana", "ua_media")
    orden = _orden(conceptos)
    filas = []
    for c in por_concepto:
        n = int(c["n_estudiantes"])
        valores = None
        if not pequeno(n, n_minimo):
            dist = c["distribucion_ns"]
            valores = {
                "n_estudiantes": n, **{f"ns{k}": int(dist.get(str(k), 0)) for k in range(4)},
                "ta_media": c.get("ta_media"), "ni_mediana": c.get("ni_mediana"),
                "tr_mediana": c.get("tr_mediana"), "ua_media": c.get("ua_media"),
            }
        filas.append(_fila({"concepto": c["concepto_codigo"]}, campos, valores))
    return sorted(filas, key=lambda f: orden.get(f["concepto"], 99))


# ---------------------------------------------------------------- ayudas
def ayudas_por_tipo(ayudas: pd.DataFrame, n_minimo: int) -> list[dict]:
    """Ayudas entregadas por tipo (AY1 a AY4) y sus valoraciones (1 = útil, -1 = no útil)."""
    campos = ("n_solicitudes", "n_estudiantes", "n_mostradas_solas", "n_respaldo", "n_valoradas", "utiles", "no_utiles", "proporcion_util")
    filas = []
    for tipo in TIPOS_AYUDA:
        g = ayudas[ayudas["tipo_ayuda"] == tipo] if not ayudas.empty else ayudas
        n = int(g["usuario_id"].nunique()) if len(g) else 0
        valores = None
        if not pequeno(n, n_minimo):
            valoradas = int(g["valoracion"].notna().sum()) if len(g) else 0
            utiles = int((g["valoracion"] == 1).sum()) if len(g) else 0
            valores = {
                "n_solicitudes": int(len(g)), "n_estudiantes": n,
                "n_mostradas_solas": int(g["mostrada_sola"].sum()) if len(g) else 0,
                "n_respaldo": int(g["fue_respaldo"].sum()) if len(g) else 0, "n_valoradas": valoradas, "utiles": utiles,
                "no_utiles": valoradas - utiles, "proporcion_util": _r(utiles / valoradas) if valoradas else None,
            }
        filas.append(_fila({"tipo": tipo}, campos, valores))
    return filas


# ---------------------------------------------------------------- retiros y refuerzos
def tipo_de_cambio(regla: str, ns_anterior: int, ns_nuevo: int, reglas_retiro: tuple[str, ...]) -> str:
    """retiro (R1/R2 bajan el NS) · recaída (R3) · refuerzo (cualquier otra subida: R5, R8, R12, R14) · otro."""
    if regla == "R3":
        return "recaida"
    if ns_nuevo > ns_anterior:
        return "refuerzo"
    if ns_nuevo < ns_anterior and regla in reglas_retiro:
        return "retiro"
    return "otro"


def retiros_y_refuerzos(
    historial: pd.DataFrame, conceptos: list[dict], reglas_retiro: tuple[str, ...],
    desde: datetime | None, hasta: datetime | None, n_minimo: int,
) -> list[dict]:
    campos = ("n_cambios", "n_estudiantes", "reglas")
    if historial.empty:
        return []
    h = historial[en_periodo(historial["creado_en"], desde, hasta)].copy()
    if h.empty:
        return []
    h["tipo"] = [tipo_de_cambio(r, a, n, reglas_retiro) for r, a, n in zip(h["regla"], h["ns_anterior"], h["ns_nuevo"])]
    orden = _orden(conceptos)
    filas = []
    for (codigo, tipo), g in h.groupby(["concepto_codigo", "tipo"]):
        n = int(g["usuario_id"].nunique())
        valores = None if pequeno(n, n_minimo) else {
            "n_cambios": int(len(g)), "n_estudiantes": n, "reglas": {k: int(v) for k, v in g["regla"].value_counts().sort_index().items()},
        }
        filas.append(_fila({"concepto": codigo, "tipo": tipo}, campos, valores))
    return sorted(filas, key=lambda f: (orden.get(f["concepto"], 99), TIPOS_CAMBIO.index(f["tipo"])))


# ---------------------------------------------------------------- línea base
def linea_base(globales: pd.DataFrame, por_concepto: pd.DataFrame, conceptos: list[dict], n_minimo: int) -> dict:
    """m medio de la línea base (global y por concepto) de quienes la completaron en el periodo."""
    n = int(globales["usuario_id"].nunique()) if len(globales) else 0
    if pequeno(n, n_minimo):
        return {"n_estudiantes": None, "m_global_media": None, "por_concepto": [], "suprimido": True}
    orden = _orden(conceptos)
    filas = []
    for codigo, g in por_concepto.groupby("concepto_codigo") if len(por_concepto) else []:
        k = int(g["usuario_id"].nunique())
        filas.append({"concepto": codigo, "m_media": None if pequeno(k, n_minimo) else _r(g["m"].mean()), "suprimido": pequeno(k, n_minimo)})
    filas.sort(key=lambda f: orden.get(f["concepto"], 99))
    return {"n_estudiantes": n, "m_global_media": _r(globales["m_global"].mean()) if n else None, "por_concepto": filas, "suprimido": False}


# ---------------------------------------------------------------- eficacia del retiro (Matriz, sección 10)
def _primero_por_par(df: pd.DataFrame) -> pd.DataFrame:
    return df.sort_values("creado_en").groupby(["usuario_id", "concepto_id"], as_index=False).head(1)


def _resumen_numerico(valores: pd.Series) -> dict:
    return {"media": _r(valores.mean()), "mediana": _r(valores.median()), "minimo": _r(valores.min()), "maximo": _r(valores.max())}


def conceptos_ns0_sin_recaida(
    historial: pd.DataFrame, reglas_retiro: tuple[str, ...], desde: datetime | None, hasta: datetime | None, n_minimo: int
) -> dict:
    """De los conceptos (estudiante + concepto) que llegan a NS 0 por retiro, ¿cuántos no tienen una recaída (R3) después?"""
    vacio = {"n_conceptos": 0, "n_estudiantes": 0, "sin_recaida": 0, "proporcion": None, "suprimido": False}
    if historial.empty:
        return vacio
    llegadas = historial[(historial["ns_nuevo"] == 0) & (historial["ns_anterior"] > 0) & historial["regla"].isin(reglas_retiro)]
    llegadas = _primero_por_par(llegadas) if len(llegadas) else llegadas
    llegadas = llegadas[en_periodo(llegadas["creado_en"], desde, hasta)] if len(llegadas) else llegadas
    if llegadas.empty:
        return vacio
    n_est = int(llegadas["usuario_id"].nunique())
    if pequeno(n_est, n_minimo):
        return {**{k: None for k in vacio}, "suprimido": True}
    recaidas = historial[(historial["regla"] == "R3") & (historial["ns_anterior"] == 0)][["usuario_id", "concepto_id", "creado_en"]]
    m = llegadas.merge(recaidas, on=["usuario_id", "concepto_id"], how="left", suffixes=("", "_r3"))
    con_recaida = m[m["creado_en_r3"] > m["creado_en"]].drop_duplicates(["usuario_id", "concepto_id"])
    total, sin = int(len(llegadas)), int(len(llegadas)) - int(len(con_recaida))
    return {"n_conceptos": total, "n_estudiantes": n_est, "sin_recaida": sin, "proporcion": _r(sin / total), "suprimido": False}


def desafios_hasta_primer_retiro(
    historial: pd.DataFrame, cierres: pd.DataFrame, conceptos: list[dict], reglas_retiro: tuple[str, ...],
    desde: datetime | None, hasta: datetime | None, n_minimo: int,
) -> dict:
    """Desafíos cerrados del concepto antes de su primer retiro (las omisiones no cuentan: no son cierres)."""
    vacio = {"n_conceptos": 0, "n_estudiantes": 0, "media": None, "mediana": None, "minimo": None, "maximo": None, "suprimido": False}
    resultado = {"global": vacio, "por_concepto": []}
    if historial.empty:
        return resultado
    retiros = historial[historial["regla"].isin(reglas_retiro) & (historial["ns_nuevo"] < historial["ns_anterior"])]
    retiros = _primero_por_par(retiros) if len(retiros) else retiros
    retiros = retiros[en_periodo(retiros["creado_en"], desde, hasta)] if len(retiros) else retiros
    if retiros.empty:
        return resultado
    pares = ["usuario_id", "concepto_id"]
    previos = retiros[pares + ["concepto_codigo", "creado_en"]].merge(
        cierres[pares + ["fin"]] if len(cierres) else pd.DataFrame(columns=pares + ["fin"]), on=pares, how="left"
    )
    previos["antes"] = (previos["fin"] <= previos["creado_en"]).astype(int)
    conteo = previos.groupby(pares + ["concepto_codigo"], as_index=False)["antes"].sum().rename(columns={"antes": "desafios"})

    def resumen(g: pd.DataFrame) -> dict:
        n = int(g["usuario_id"].nunique())
        if pequeno(n, n_minimo):
            return {**{k: None for k in vacio}, "suprimido": True}
        return {"n_conceptos": int(len(g)), "n_estudiantes": n, **_resumen_numerico(g["desafios"]), "suprimido": False}

    resultado["global"] = resumen(conteo)
    orden = _orden(conceptos)
    por = [{"concepto": codigo, **resumen(g)} for codigo, g in conteo.groupby("concepto_codigo")]
    resultado["por_concepto"] = sorted(por, key=lambda f: orden.get(f["concepto"], 99))
    return resultado


def sa_por_bloque(cierres: pd.DataFrame, tamano: int, desde: datetime | None, hasta: datetime | None, n_minimo: int) -> list[dict]:
    """Proporción de SA según el orden de los desafíos del estudiante (bloques de `tamano`): ¿sube a medida que se retira la ayuda?"""
    if cierres.empty:
        return []
    c = cierres.sort_values(["fin", "sesion_id"]).copy()
    c["orden"] = c.groupby("usuario_id").cumcount() + 1  # el orden se cuenta sobre toda la historia
    c = c[en_periodo(c["fin"], desde, hasta)]
    c["bloque"] = (c["orden"] - 1) // tamano
    filas = []
    for bloque, g in c.groupby("bloque"):
        n = int(g["usuario_id"].nunique())
        base = {"desde_orden": int(bloque) * tamano + 1, "hasta_orden": (int(bloque) + 1) * tamano}
        if pequeno(n, n_minimo):
            filas.append({**base, "n_estudiantes": None, "n_desafios": None, "proporcion_sa": None, "suprimido": True})
        else:
            filas.append({**base, "n_estudiantes": n, "n_desafios": int(len(g)), "proporcion_sa": _r((g["resultado"] == "SA").mean()), "suprimido": False})
    return filas


def activacion_r9_r10(activaciones: pd.DataFrame, n_sesiones: int, n_minimo: int, reglas: tuple[str, ...] = ("R9", "R10")) -> list[dict]:
    """Cuántas veces se activaron la dependencia (R9) y el ensayo y error (R10), y en qué proporción de las sesiones."""
    campos = ("n_activaciones", "n_estudiantes", "n_sesiones", "proporcion_sesiones")
    filas = []
    for regla in reglas:
        g = activaciones[activaciones["regla"] == regla] if len(activaciones) else activaciones
        n = int(g["usuario_id"].nunique()) if len(g) else 0
        valores = None
        if not pequeno(n, n_minimo):
            ses = int(g["sesion_id"].nunique()) if len(g) else 0
            valores = {
                "n_activaciones": int(len(g)), "n_estudiantes": n, "n_sesiones": ses,
                "proporcion_sesiones": _r(min(ses / n_sesiones, 1.0)) if n_sesiones else None,
            }
        filas.append(_fila({"regla": regla}, campos, valores))
    return filas


def precision_ns_inicial(
    historial: pd.DataFrame, cierres: pd.DataFrame, minimo_desafios: int, reglas_retiro: tuple[str, ...],
    reglas_refuerzo: tuple[str, ...], desde: datetime | None, hasta: datetime | None, n_minimo: int,
) -> dict:
    """¿Coincide el NS inicial con el desempeño en los primeros desafíos? (PROVISIONAL, ver docs/DECISIONES.md)

    Para cada estudiante-concepto: si el motor cambia el NS por desempeño (retiro R1/R2 o refuerzo R5/R8) dentro de los
    primeros `minimo_desafios` cierres, el NS inicial no coincidía (retiro = era más alto de lo necesario; refuerzo = más
    bajo); si llega a esos cierres sin cambio, coincide. Con menos cierres y sin cambio no se evalúa.
    """
    vacio = {"n_conceptos": 0, "n_estudiantes": 0, "coincide": 0, "inicial_alto": 0, "inicial_bajo": 0, "proporcion_coincide": None, "suprimido": False}
    if cierres.empty and historial.empty:
        return vacio
    pares = ["usuario_id", "concepto_id"]
    fin_k = {}
    previos = {}
    for (u, c), g in cierres.groupby(pares):
        fines = list(g["fin"])  # ya vienen ordenados
        previos[(u, c)] = fines
        if len(fines) >= minimo_desafios:
            fin_k[(u, c)] = fines[minimo_desafios - 1]
    por_desempeno = historial[
        (historial["regla"].isin(reglas_retiro) & (historial["ns_nuevo"] < historial["ns_anterior"]))
        | (historial["regla"].isin(reglas_refuerzo) & (historial["ns_nuevo"] > historial["ns_anterior"]))
    ]
    primer_cambio = {}
    for fila in _primero_por_par(por_desempeno).itertuples(index=False) if len(por_desempeno) else []:
        primer_cambio[(fila.usuario_id, fila.concepto_id)] = (fila.creado_en, "inicial_alto" if fila.ns_nuevo < fila.ns_anterior else "inicial_bajo")
    resultados: list[tuple[int, str]] = []  # (usuario, categoría)
    for par in set(fin_k) | set(primer_cambio):
        categoria, momento = None, None
        if par in primer_cambio:
            t, tipo = primer_cambio[par]
            if sum(1 for f in previos.get(par, []) if f <= t) <= minimo_desafios:
                categoria, momento = tipo, t
        if categoria is None and par in fin_k:
            categoria, momento = "coincide", fin_k[par]
        if categoria is None:
            continue
        if (desde is not None and momento < pd.Timestamp(desde)) or (hasta is not None and momento > pd.Timestamp(hasta)):
            continue
        resultados.append((par[0], categoria))
    if not resultados:
        return vacio
    n_est = len({u for u, _ in resultados})
    if pequeno(n_est, n_minimo):
        return {**{k: None for k in vacio}, "suprimido": True}
    cuenta = {k: sum(1 for _, c in resultados if c == k) for k in ("coincide", "inicial_alto", "inicial_bajo")}
    return {"n_conceptos": len(resultados), "n_estudiantes": n_est, **cuenta, "proporcion_coincide": _r(cuenta["coincide"] / len(resultados)), "suprimido": False}
