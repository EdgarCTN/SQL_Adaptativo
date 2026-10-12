import logging

from app.core.config import Settings, settings
from app.modules.asistencia.llm.base import LLMProvider
from app.modules.asistencia.llm.mock import MockLLMProvider
from app.modules.asistencia.llm.proveedores_externos import AnthropicProvider, OpenAIProvider

log = logging.getLogger("app.llm")


def obtener_proveedor(cfg: Settings | None = None) -> LLMProvider:
    """Elige el proveedor según LLM_PROVIDER (por defecto «mock»). Un valor desconocido usa el mock."""
    cfg = cfg or settings
    nombre = cfg.llm_provider.strip().lower()
    if nombre == "anthropic":
        return AnthropicProvider(cfg.anthropic_api_key, cfg.llm_model)
    if nombre == "openai":
        return OpenAIProvider()
    if nombre != "mock":
        log.warning("LLM_PROVIDER=%r no es válido: se usa «mock».", cfg.llm_provider)
    return MockLLMProvider()
