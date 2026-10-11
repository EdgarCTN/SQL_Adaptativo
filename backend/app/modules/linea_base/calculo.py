"""Cálculo puro (sin BD) de m, NS inicial y banderas de la línea base. Todos los valores vienen de reglas.json."""
from dataclasses import dataclass, field
from statistics import fmean

from app.modules.linea_base.schemas import RespuestaIn
from app.modules.motor_retiro.niveles import NS_POR_DEFECTO

# Estructura del cuestionario (no son valores de la Matriz)
OPCIONES_1_6_RIESGO = frozenset({"c", "d"})  # «obtener la consulta ya resuelta» y «ambas formas»
CODIGO_INMEDIATO = "inmediato"  # 3.2 y 3.6


def _r(x: float) -> float:
    return round(x, 6)  # evita errores de coma flotante en los cortes (p. ej. 0.7 exacto)


@dataclass
class ResultadoLineaBase:
    m_por_item: dict = field(default_factory=dict)
    m_por_concepto: dict = field(default_factory=dict)
    m_por_nivel: dict = field(default_factory=dict)
    m_global: float | None = None
    ns_inicial: dict = field(default_factory=dict)  # código de concepto → NS que se aplica
    ajuste_3_1: dict = field(default_factory=dict)  # código → NS tras la preferencia 3.1 (NO se aplica)
    dificultad_inicial: str | None = None  # NO se aplica
    banderas: dict = field(default_factory=dict)  # r9, r11 (NO se aplican)
    preferencias: dict = field(default_factory=dict)  # Parte 3: 3.1 a 3.6 como códigos
    contexto: dict = field(default_factory=dict)  # Parte 1 cruda


def valor_m(reglas: dict, info, r: RespuestaIn) -> tuple[float, str]:
    """Devuelve (m del ítem, resultado) según la Tabla 15."""
    v = reglas["valor_dominio_m"]
    if r.omitir == "muy_facil":
        return v["omision_muy_facil"], "omision_muy_facil"
    if r.omitir == "muy_dificil":
        return v["omision_muy_dificil"], "omision_muy_dificil"
    if info.opciones[r.opciones[0]].get("es_no_se"):
        return v["no_se"], "no_se"
    if r.opciones[0] == info.correcta:
        return v["acierta"][str(r.confianza)], "acierto"
    return v["se_equivoca"][str(r.confianza)], "error"


def ns_desde_m(m: float, cortes: dict) -> int:
    if m >= cortes["ns0_m_minimo"]:
        return 0
    if m >= cortes["ns1_m_minimo"]:
        return 1
    return 2


def ajustar_por_3_1(ns: int, preferencia: str | None) -> int:
    """Ajuste R0 por la preferencia 3.1: el resultado queda entre NS1 y NS2; NS0 no se toca."""
    if ns not in (1, 2):
        return ns
    if preferencia == "AY1":
        return max(1, ns - 1)
    if preferencia in ("AY3", "AY4"):
        return min(2, ns + 1)
    return ns


def _dificultad_inicial(m_por_nivel: dict, minimo: float) -> str:
    for dificultad in sorted(m_por_nivel):
        if dificultad == "D3":
            break
        if m_por_nivel[dificultad] < minimo:
            return dificultad
    return "D3"


def calcular_linea_base(
    indice: list, respuestas: dict[str, RespuestaIn], conceptos: list[str], reglas: dict
) -> ResultadoLineaBase:
    res = ResultadoLineaBase()
    cortes = reglas["cortes_linea_base"]

    por_concepto: dict[str, list[float]] = {}
    resultados_concepto: dict[str, list[str]] = {}
    por_nivel: dict[str, list[float]] = {}
    errores_altos = 0
    altos = set(reglas["r11_sobreconfianza"]["confianza_alta"])

    for info in indice:
        r = respuestas.get(info.id)
        if r is None:
            continue
        if info.parte == 1:
            res.contexto[info.id] = list(r.opciones)
        elif info.parte == 3:
            res.preferencias[info.id] = info.opciones[r.opciones[0]].get("codigo")
        elif info.tipo == "prueba":
            m, resultado = valor_m(reglas, info, r)
            m = _r(m)
            res.m_por_item[info.id] = {
                "m": m,
                "resultado": resultado,
                "confianza": r.confianza if resultado in ("acierto", "error") else None,
                "concepto": info.concepto,
                "nivel": info.nivel,
            }
            por_concepto.setdefault(info.concepto, []).append(m)
            resultados_concepto.setdefault(info.concepto, []).append(resultado)
            por_nivel.setdefault(info.dificultad or f"D{info.nivel}", []).append(m)
            if resultado == "error" and r.confianza in altos:
                errores_altos += 1

    todos = [x["m"] for x in res.m_por_item.values()]
    res.m_global = _r(fmean(todos)) if todos else None
    res.m_por_nivel = {k: _r(fmean(v)) for k, v in sorted(por_nivel.items())}
    res.dificultad_inicial = (
        _dificultad_inicial(res.m_por_nivel, cortes["dominio_por_nivel_minimo"]) if res.m_por_nivel else None
    )

    pref_3_1 = res.preferencias.get("3.1")
    for codigo in conceptos:
        valores = por_concepto.get(codigo, [])
        todas_muy_facil = bool(valores) and all(x == "omision_muy_facil" for x in resultados_concepto[codigo])
        if valores:
            m, origen = _r(fmean(valores)), "items"
        else:  # concepto sin ítems: usa el promedio global
            m, origen = res.m_global, "global"
        res.m_por_concepto[codigo] = {
            "m": m,
            "n_items": len(valores),
            "origen": origen,
            "todas_muy_facil": todas_muy_facil,
        }
        if todas_muy_facil:
            ns = 1  # excepción simple de R0
        elif m is None:
            ns = NS_POR_DEFECTO
        else:
            ns = ns_desde_m(m, cortes)
        res.ns_inicial[codigo] = ns
        res.ajuste_3_1[codigo] = ns if todas_muy_facil else ajustar_por_3_1(ns, pref_3_1)

    senales = {
        "1.6": bool(set(res.contexto.get("1.6", [])) & OPCIONES_1_6_RIESGO),
        "3.2": res.preferencias.get("3.2") == CODIGO_INMEDIATO,
        "3.6": res.preferencias.get("3.6") == CODIGO_INMEDIATO,
    }
    cumplidas = sum(senales.values())
    res.banderas = {
        "r9": {
            "riesgo": cumplidas >= reglas["r9_dependencia"]["senales_linea_base_minimas"],
            "senales": senales,
            "senales_cumplidas": cumplidas,
        },
        "r11": {
            "errores_confianza_alta": errores_altos,
            "sobreconfianza": errores_altos >= reglas["r11_sobreconfianza"]["errores_con_confianza_alta_minimos"],
        },
        "ajuste_ns_3_1": res.ajuste_3_1,
    }
    return res
