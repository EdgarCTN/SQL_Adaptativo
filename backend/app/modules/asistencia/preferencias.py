from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.asistencia.config_llm import cargar_plantillas
from app.modules.asistencia.prompt_builder import TONO_POR_DEFECTO
from app.modules.linea_base.models import LineaBaseResultado


def tono_guardado(db: Session, usuario_id: int) -> str:
    """Tono elegido en el diagnóstico (pregunta 3.5), o «directo» si no existe o no es válido."""
    prefs = db.scalar(select(LineaBaseResultado.preferencias).where(LineaBaseResultado.usuario_id == usuario_id))
    codigo = (prefs or {}).get("3.5") if isinstance(prefs, dict) else None
    return codigo if codigo in cargar_plantillas()["tonos"] else TONO_POR_DEFECTO
