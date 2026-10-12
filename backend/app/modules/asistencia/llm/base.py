from abc import ABC, abstractmethod
from dataclasses import dataclass


class NoConfigurado(Exception):
    """El proveedor existe pero todavía no se puede usar."""


@dataclass(frozen=True)
class SolicitudLLM:
    tipo_ayuda: str  # AY1..AY4
    prompt_sistema: str
    mensaje_usuario: str
    ayuda_respaldo: dict | None = None  # {"mensaje", "codigo_sql"} del desafío; solo lo usa el mock/respaldo


@dataclass(frozen=True)
class RespuestaLLM:
    texto: str  # JSON con tipo_entregado, mensaje, codigo_sql (lo valida la entrega 7B)
    proveedor: str
    es_respaldo: bool = False  # True: mock o ayuda de respaldo (modo demostración)
    etiquetas: tuple[str, ...] = ()  # rótulos que debe mostrar la ayuda (salen de llm.json)


class LLMProvider(ABC):
    """Contrato común de los proveedores (RNF-21). Nunca debe recibir datos personales del estudiante."""

    nombre: str

    @abstractmethod
    def generar(self, solicitud: SolicitudLLM) -> RespuestaLLM: ...
