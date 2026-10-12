"""Construye el prompt del LLM a partir de config/plantillas_llm.json y config/llm.json.

Privacidad: la función solo recibe los datos permitidos (tipo, tono, banderas, concepto, dificultad,
enunciado, esquema, errores típicos, estado del desafío, código, resultado, mensaje opcional y,
solo en AY3/AY4, la solución). No existe parámetro para nombre, correo, NS ni indicadores de ventana.
"""
import re
from dataclasses import dataclass, field

from app.modules.asistencia.config_llm import cargar_llm, cargar_plantillas

TIPOS = ("AY1", "AY2", "AY3", "AY4")
TIPOS_SIN_SOLUCION = ("AY1", "AY2")  # la línea <solucion_referencia> se omite (nota de plantillas_llm.json)
TONO_POR_DEFECTO = "directo"
_MARCADOR = re.compile(r"\{\{(\w+)\}\}")


@dataclass
class DatosPrompt:
    tipo_ayuda: str
    concepto: str
    dificultad: str
    enunciado: str
    esquema_sql: str
    errores_tipicos: list[str] = field(default_factory=list)
    intento: int = 0
    fallos: int = 0
    tiempo_relativo: float | None = None  # tiempo transcurrido / tiempo de referencia del desafío
    ayudas_previas: list[str] = field(default_factory=list)
    codigo_estudiante: str = ""
    resultado_obtenido: str = ""
    mensaje_estudiante: str = ""
    solucion_referencia: str = ""
    tono: str | None = None
    banderas: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PromptLLM:
    prompt_sistema: str
    mensaje_usuario: str


def descripciones_errores(errores_tipicos: list | None) -> list[str]:
    """Acepta los errores típicos guardados ({descripcion, ejemplo}) o textos simples; solo pasa la descripción."""
    salida = []
    for e in errores_tipicos or []:
        texto = e.get("descripcion") if isinstance(e, dict) else e
        if texto:
            salida.append(str(texto))
    return salida


def _neutralizar(texto: str, etiquetas: set[str]) -> str:
    """Evita que el texto del estudiante cierre o abra las etiquetas de la plantilla."""
    if not etiquetas:
        return texto
    patron = re.compile(r"</?\s*(?:" + "|".join(re.escape(t) for t in sorted(etiquetas)) + r")\s*>", re.IGNORECASE)
    return patron.sub(lambda m: m.group(0).replace("<", "< ", 1), texto)


def construir_prompt(datos: DatosPrompt, plantillas: dict | None = None, llm: dict | None = None) -> PromptLLM:
    plantillas = plantillas or cargar_plantillas()
    llm = llm or cargar_llm()
    tipo = datos.tipo_ayuda
    if tipo not in TIPOS or tipo not in plantillas["bloques_tipo"]:
        raise ValueError(f"Tipo de ayuda desconocido: {tipo!r}")
    tono = datos.tono if datos.tono in plantillas["tonos"] else TONO_POR_DEFECTO
    desconocidas = [b for b in datos.banderas if b not in plantillas["banderas"]]
    if desconocidas:
        raise ValueError(f"Banderas desconocidas: {', '.join(desconocidas)}")

    # --- Prompt de sistema: sistema + bloque del tipo + tono + banderas ---
    partes = [
        plantillas["sistema"],
        f"{plantillas['etiquetas_bloque'][tipo]}\n{plantillas['bloques_tipo'][tipo]}",
        f"[TONO: {tono}]\n{plantillas['tonos'][tono]}",
    ]
    partes += [f"[BANDERA: {b}]\n{plantillas['banderas'][b]}" for b in dict.fromkeys(datos.banderas)]
    prompt_sistema = "\n\n".join(partes)

    # --- Mensaje de usuario: mensaje_datos con los marcadores reemplazados ---
    plantilla = plantillas["mensaje_datos"]
    etiquetas = set(re.findall(r"</?([A-Za-z_]+)>", plantilla))
    if tipo in TIPOS_SIN_SOLUCION:
        plantilla = "\n".join(l for l in plantilla.split("\n") if "{{solucion_referencia}}" not in l)
    codigo = (datos.codigo_estudiante or "")[: int(llm["max_chars_codigo_estudiante"])]
    mensaje = (datos.mensaje_estudiante or "")[: int(llm["max_chars_mensaje_estudiante"])]
    valores = {
        "tipo_ayuda": tipo,
        "tono": tono,
        "banderas": ", ".join(dict.fromkeys(datos.banderas)) or "ninguna",
        "concepto": datos.concepto,
        "dificultad": datos.dificultad,
        "enunciado": datos.enunciado,
        "esquema_sql": datos.esquema_sql,
        "errores_tipicos_del_concepto": "\n".join(f"- {e}" for e in datos.errores_tipicos) or "ninguno",
        "intento": str(datos.intento),
        "fallos": str(datos.fallos),
        "tiempo_relativo": "desconocido" if datos.tiempo_relativo is None else f"{datos.tiempo_relativo:.1f}",
        "ayudas_previas": "; ".join(datos.ayudas_previas) or "ninguna",
        "codigo_estudiante": _neutralizar(codigo, etiquetas),
        "resultado_obtenido": _neutralizar(datos.resultado_obtenido or "", etiquetas),
        "mensaje_estudiante": _neutralizar(mensaje, etiquetas),
        "solucion_referencia": datos.solucion_referencia or "",
    }

    def sustituir(m: re.Match) -> str:
        try:
            return valores[m.group(1)]
        except KeyError:
            raise ValueError(f"La plantilla usa un marcador desconocido: {{{{{m.group(1)}}}}}") from None

    return PromptLLM(prompt_sistema, _MARCADOR.sub(sustituir, plantilla))
