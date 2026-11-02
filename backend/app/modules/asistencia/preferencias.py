from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.reglas import cargar_reglas
from app.modules.asistencia.config_llm import cargar_plantillas
from app.modules.asistencia.prompt_builder import TONO_POR_DEFECTO
from app.modules.linea_base.models import LineaBaseResultado


def tono_guardado(db: Session, usuario_id: int) -> str:
    """Tono elegido en el diagnóstico (pregunta 3.5), o «directo» si no existe o no es válido."""
    prefs = db.scalar(select(LineaBaseResultado.preferencias).where(LineaBaseResultado.usuario_id == usuario_id))
    codigo = (prefs or {}).get("3.5") if isinstance(prefs, dict) else None
    return codigo if codigo in cargar_plantillas()["tonos"] else TONO_POR_DEFECTO


MODOS_AYUDA = ("a_solicitud", "ofrecer", "mostrar_sola")  # códigos de la pregunta 3.3 del diagnóstico


def preferencia_ayuda(db: Session, usuario_id: int) -> str:
    """Pregunta 3.3 (cómo recibir la ayuda). Sin respuesta o con un código desconocido: `r13_preferencia_ayuda.por_defecto`
    de reglas.json (PROVISIONAL: «ofrecer», el comportamiento que describe la Tabla 11)."""
    prefs = db.scalar(select(LineaBaseResultado.preferencias).where(LineaBaseResultado.usuario_id == usuario_id))
    codigo = prefs.get("3.3") if isinstance(prefs, dict) else None
    if codigo in MODOS_AYUDA:
        return codigo
    try:
        por_defecto = cargar_reglas()["r13_preferencia_ayuda"]["por_defecto"]
    except (OSError, ValueError, KeyError, TypeError):
        por_defecto = "ofrecer"
    return por_defecto if por_defecto in MODOS_AYUDA else "ofrecer"
