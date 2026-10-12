import logging

import httpx

from app.modules.asistencia.config_llm import cargar_llm
from app.modules.asistencia.llm.base import LLMProvider, NoConfigurado, RespuestaLLM, SolicitudLLM
from app.modules.asistencia.llm.mock import MockLLMProvider

log = logging.getLogger("app.llm")
URL_ANTHROPIC = "https://api.anthropic.com/v1/messages"
VERSION_API_ANTHROPIC = "2023-06-01"


class AnthropicProvider(LLMProvider):
    """Llama a la API de Anthropic. Sin clave, o ante cualquier fallo o demora, cae al mock sin error.

    No se probó contra la API real (aún no hay clave): solo con un cliente HTTP simulado.
    """

    nombre = "anthropic"

    def __init__(
        self,
        api_key: str,
        modelo: str,
        cliente: httpx.Client | None = None,
        respaldo: LLMProvider | None = None,
    ):
        self._api_key = (api_key or "").strip()
        self._modelo = modelo
        self._cliente = cliente
        self._respaldo = respaldo or MockLLMProvider()

    def generar(self, solicitud: SolicitudLLM) -> RespuestaLLM:
        if not self._api_key:
            log.warning("ANTHROPIC_API_KEY vacía: se usa el modo demostración.")
            return self._respaldo.generar(solicitud)
        try:
            cfg = cargar_llm()  # temperatura, tokens por tipo y tiempo límite salen de llm.json
            cuerpo = {
                "model": self._modelo,
                "max_tokens": cfg["max_tokens"][solicitud.tipo_ayuda],
                "temperature": cfg["temperatura"],
                "system": solicitud.prompt_sistema,
                "messages": [{"role": "user", "content": solicitud.mensaje_usuario}],
            }
            cabeceras = {
                "x-api-key": self._api_key,
                "anthropic-version": VERSION_API_ANTHROPIC,
                "content-type": "application/json",
            }
            cliente = self._cliente or httpx.Client()
            try:
                r = cliente.post(URL_ANTHROPIC, headers=cabeceras, json=cuerpo, timeout=cfg["tiempo_limite_seg"])
            finally:
                if self._cliente is None:
                    cliente.close()
            r.raise_for_status()
            bloques = r.json().get("content", [])
            texto = "".join(b.get("text", "") for b in bloques if b.get("type") == "text").strip()
            if not texto:
                raise ValueError("respuesta vacía")
            return RespuestaLLM(texto, self.nombre, es_respaldo=False, etiquetas=(cfg["etiqueta_ia"],))
        except Exception as e:  # noqa: BLE001  (red, HTTP, JSON o formato: nunca llega al estudiante)
            log.warning("Falló la llamada al LLM (%s): se usa el modo demostración.", type(e).__name__)
            return self._respaldo.generar(solicitud)


class OpenAIProvider(LLMProvider):
    """Solo la firma: todavía no está implementado."""

    nombre = "openai"

    def generar(self, solicitud: SolicitudLLM) -> RespuestaLLM:
        raise NoConfigurado("El proveedor OpenAI no está configurado.")
