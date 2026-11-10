"""Controles V1–V9. AY2 se analiza; únicamente AY4 se ejecuta en el sandbox."""
import json
import re
from dataclasses import dataclass
from typing import Callable

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from langdetect import DetectorFactory, LangDetectException, detect_langs

from app.modules.asistencia.config_llm import cargar_llm
from app.modules.desafios.sandbox import evaluar_consulta

DetectorFactory.seed = 0


@dataclass
class ContextoValidacion:
    texto: str
    tipo_pedido: str
    datos: dict | None = None
    solucion: str = ""
    esquema: str = ""
    setup: str = ""
    segundos: float = 0
    limite_seg: float = 8
    personales: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResultadoValidacion:
    ok: bool
    motivo: str | None = None
    datos: dict | None = None


def _quitar_cercas(texto: str) -> str:
    m = re.fullmatch(r"\s*```(?:json)?\s*(.*?)\s*```\s*", texto, flags=re.DOTALL | re.IGNORECASE)
    return m.group(1) if m else texto


def v1_json_valido(ctx: ContextoValidacion) -> str | None:
    try:
        datos = json.loads(_quitar_cercas(ctx.texto or ""))
    except (ValueError, TypeError):
        return "V1: la respuesta no es un JSON válido"
    if not isinstance(datos, dict):
        return "V1: la respuesta no es un objeto JSON"
    faltan = [k for k in ("tipo_entregado", "mensaje", "codigo_sql") if k not in datos]
    if faltan:
        return f"V1: faltan los campos {', '.join(faltan)}"
    if not isinstance(datos["tipo_entregado"], str):
        return "V1: tipo_entregado debe ser texto"
    if not isinstance(datos["mensaje"], str) or not datos["mensaje"].strip():
        return "V1: el mensaje está vacío"
    if datos["codigo_sql"] is not None and not isinstance(datos["codigo_sql"], str):
        return "V1: codigo_sql debe ser texto o null"
    ctx.datos = datos
    return None


def v2_tipo_entregado(ctx: ContextoValidacion) -> str | None:
    if ctx.datos["tipo_entregado"] != ctx.tipo_pedido:
        return f"V2: tipo_entregado es {ctx.datos['tipo_entregado']!r} y se pidió {ctx.tipo_pedido}"
    return None


def _normalizar(sql: str) -> str:
    return " ".join(t.text.casefold() for t in sqlglot.tokenize(sql, read="sqlite") if t.text != ";")


def _revela_solucion(ctx: ContextoValidacion) -> bool:
    return bool(ctx.solucion and _normalizar(ctx.solucion) in _normalizar(
        ctx.datos["mensaje"] + " " + (ctx.datos["codigo_sql"] or "")))


def v3_pista_sin_codigo(ctx: ContextoValidacion) -> str | None:
    if ctx.tipo_pedido != "AY1":
        return None
    if (ctx.datos["codigo_sql"] or "").strip() or "```" in ctx.datos["mensaje"] or re.search(
        r"\b(?:SELECT|FROM|WHERE|HAVING|JOIN|GROUP\s+BY|ORDER\s+BY|LIMIT)\b|\b(?:COUNT|SUM|AVG|MIN|MAX)\s*\(",
        ctx.datos["mensaje"], re.I,
    ) or _revela_solucion(ctx):
        return "V3: AY1 debe orientar sin código, cláusulas exactas ni solución"
    return None


def _consulta(sql: str):
    sentencias = sqlglot.parse(sql, read="sqlite", error_level=sqlglot.ErrorLevel.RAISE)
    if len(sentencias) != 1 or not isinstance(sentencias[0], exp.Query):
        raise ValueError("Se requiere una única consulta de lectura")
    return sentencias[0]


def v4_ejemplo_otro_contexto(ctx: ContextoValidacion) -> str | None:
    if ctx.tipo_pedido != "AY2":
        return None
    try:
        consulta = _consulta(ctx.datos["codigo_sql"] or "")
        arboles = []
        # El esquema visible puede ser abreviado (p. ej. «CREATE TABLE libros (...)»).
        # El setup de SQLite, cuando existe, aporta la definición completa de referencia.
        for fuente in (ctx.esquema, ctx.setup):
            if not fuente:
                continue
            try:
                arboles.extend(a for a in sqlglot.parse(fuente, read="sqlite") if a)
            except SqlglotError:
                continue
        tablas = {t.name.casefold() for arbol in arboles for t in arbol.find_all(exp.Table)}
        columnas = {c.name.casefold() for arbol in arboles for c in arbol.find_all(exp.ColumnDef)}
        if any(t.name.casefold() in tablas for t in consulta.find_all(exp.Table)) or any(
            c.name.casefold() in columnas for c in consulta.find_all(exp.Column)
        ) or _revela_solucion(ctx):
            return "V4: AY2 debe usar otras tablas y columnas sin resolver el desafío"
    except (SqlglotError, ValueError):
        return "V4: el ejemplo debe contener una única consulta SQL de lectura sintácticamente válida"
    return None


def v5_esqueleto_incompleto(ctx: ContextoValidacion) -> str | None:
    if ctx.tipo_pedido != "AY3":
        return None
    codigo = ctx.datos["codigo_sql"] or ""
    if codigo.count("___") < 2 or _revela_solucion(ctx):
        return "V5: AY3 necesita al menos dos espacios ___ y no puede revelar la solución completa"
    if ctx.solucion:
        fragmentos = [_normalizar(p) for p in codigo.split("___")]
        patron = r"\s*.+?\s*".join(re.escape(p) for p in fragmentos)
        if not re.fullmatch(patron, _normalizar(ctx.solucion), flags=re.S):
            return "V5: los fragmentos visibles deben coincidir en orden con la solución de referencia"
    return None


def v6_solucion_correcta(ctx: ContextoValidacion) -> str | None:
    if ctx.tipo_pedido != "AY4":
        return None
    if not ctx.setup or not ctx.solucion or not evaluar_consulta(
        ctx.setup, ctx.solucion, ctx.datos["codigo_sql"] or ""
    ).correcto:
        return "V6: AY4 debe ejecutarse en el sandbox y producir el resultado esperado"
    return None


def v7_extension_idioma(ctx: ContextoValidacion) -> str | None:
    mensaje = re.sub(r"```.*?```|`[^`]*`", "", ctx.datos["mensaje"], flags=re.S)
    palabras = re.findall(r"[^\W\d_]+", mensaje.casefold())
    if len(palabras) > cargar_llm()["max_palabras"][ctx.tipo_pedido]:
        return "V7: el mensaje supera el máximo de palabras del tipo de ayuda"
    # Los textos cortos son ambiguos para el detector; se exige una señal léxica española.
    if len(palabras) < 8:
        espanolas = {"el", "la", "los", "las", "en", "de", "que", "qué", "tu", "una", "un", "para",
                     "piensa", "revisa", "completa", "consulta", "ayuda", "bien", "vez", "condiciones", "corto"}
        es_espanol = bool(set(palabras) & espanolas)
    else:
        try:
            es_espanol = any(p.lang == "es" and p.prob >= 0.5 for p in detect_langs(mensaje))
        except LangDetectException:
            es_espanol = False
    return None if es_espanol else "V7: el mensaje debe estar escrito en español"


def v8_privacidad(ctx: ContextoValidacion) -> str | None:
    texto = ctx.datos["mensaje"] + " " + (ctx.datos["codigo_sql"] or "")
    if re.search(r"\bNS\b|nivel[ _]+(?:de[ _]+)?soporte|\bretiro\b|\bumbral\w*\b|\bR(?:1[0-4]|[0-9])\b|\b(?:TA|NI|TR|UA)\s*[:=]", texto, re.I):
        return "V8: no se pueden revelar reglas ni indicadores internos"
    if re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}|https?://|www\.", texto, re.I) or any(
        p.strip() and re.search(r"(?<!\w)" + re.escape(p.strip()) + r"(?!\w)", texto, re.I) for p in ctx.personales
    ):
        return "V8: la ayuda no puede contener datos personales ni enlaces"
    return None


def v9_latencia(ctx: ContextoValidacion) -> str | None:
    return "V9: tiempo límite de ayuda agotado" if ctx.segundos > ctx.limite_seg else None


VALIDACIONES: list[Callable[[ContextoValidacion], str | None]] = [
    v1_json_valido, v2_tipo_entregado, v3_pista_sin_codigo, v4_ejemplo_otro_contexto,
    v5_esqueleto_incompleto, v6_solucion_correcta, v7_extension_idioma, v8_privacidad, v9_latencia,
]


def validar(texto: str, tipo_pedido: str, **contexto) -> ResultadoValidacion:
    ctx = ContextoValidacion(texto=texto, tipo_pedido=tipo_pedido, **contexto)
    # V9 tiene prioridad, incluso ante JSON inválido: no debe provocar otro intento.
    motivo = v9_latencia(ctx)
    if motivo:
        return ResultadoValidacion(False, motivo)
    try:
        for validacion in VALIDACIONES:
            motivo = validacion(ctx)
            if motivo:
                return ResultadoValidacion(False, motivo)
    except (SqlglotError, ValueError):
        return ResultadoValidacion(False, "V3–V6: no fue posible validar el SQL de la ayuda")
    return ResultadoValidacion(True, None, ctx.datos)
