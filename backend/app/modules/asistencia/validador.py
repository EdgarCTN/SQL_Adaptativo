"""Validación de la respuesta del LLM. Hoy V1 y V2; para sumar V3–V9 basta con añadir una función a VALIDACIONES.

Cada validación recibe el ContextoValidacion y devuelve el motivo del fallo (texto) o None si pasa.
"""
import json
import re
from dataclasses import dataclass
from typing import Callable


@dataclass
class ContextoValidacion:
    texto: str
    tipo_pedido: str
    datos: dict | None = None  # lo llena V1; las siguientes validaciones lo usan


@dataclass(frozen=True)
class ResultadoValidacion:
    ok: bool
    motivo: str | None = None  # p. ej. "V1: no es un JSON válido"
    datos: dict | None = None


def _quitar_cercas(texto: str) -> str:
    """Tolera que el modelo envuelva el JSON en una cerca de código (```json ... ```)."""
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


# Orden de ejecución: se detiene en el primer fallo. Aquí se agregan V3–V9.
VALIDACIONES: list[Callable[[ContextoValidacion], str | None]] = [v1_json_valido, v2_tipo_entregado]


def validar(texto: str, tipo_pedido: str) -> ResultadoValidacion:
    ctx = ContextoValidacion(texto=texto, tipo_pedido=tipo_pedido)
    for validacion in VALIDACIONES:
        motivo = validacion(ctx)
        if motivo:
            return ResultadoValidacion(False, motivo)
    return ResultadoValidacion(True, None, ctx.datos)
