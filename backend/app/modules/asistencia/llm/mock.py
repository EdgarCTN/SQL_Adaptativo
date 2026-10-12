import json

from app.modules.asistencia.config_llm import cargar_llm
from app.modules.asistencia.llm.base import LLMProvider, RespuestaLLM, SolicitudLLM

# Provisional: texto genérico cuando el desafío no trae ayuda de respaldo para ese tipo.
TEXTO_GENERICO = (
    "Vuelve a leer el enunciado y el esquema, y comprueba paso a paso qué devuelve cada parte de tu consulta."
)


class MockLLMProvider(LLMProvider):
    """Modo demostración: devuelve la ayuda de respaldo del desafío para el tipo pedido."""

    nombre = "mock"

    def generar(self, solicitud: SolicitudLLM) -> RespuestaLLM:
        respaldo = solicitud.ayuda_respaldo or {}
        cuerpo = {
            "tipo_entregado": solicitud.tipo_ayuda,
            "mensaje": respaldo.get("mensaje") or TEXTO_GENERICO,
            "codigo_sql": respaldo.get("codigo_sql"),
        }
        cfg = cargar_llm()
        etiquetas = (cfg["etiqueta_ia"], cfg["etiqueta_mock"])
        return RespuestaLLM(json.dumps(cuerpo, ensure_ascii=False), self.nombre, es_respaldo=True, etiquetas=etiquetas)
