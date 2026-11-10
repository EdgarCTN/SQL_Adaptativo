import logging

import httpx

from app.modules.asistencia.config_llm import cargar_llm
from app.modules.asistencia.llm.base import LLMProvider, RespuestaLLM, SolicitudLLM
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
                r = cliente.post(URL_ANTHROPIC, headers=cabeceras, json=cuerpo, timeout=solicitud.tiempo_limite_seg or cfg["tiempo_limite_seg"])
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


class GroqProvider(LLMProvider):
    """Llama a Groq (por defecto openai/gpt-oss-120b) con el SDK oficial ``groq``.

    Sin clave, sin el paquete instalado, o ante cualquier fallo o demora, cae al mock sin error.
    Los modelos gpt-oss «piensan» antes de responder y esos tokens cuentan dentro de
    ``max_completion_tokens``: por eso se suma el margen de ``llm.json`` → ``razonamiento`` al tope de cada tipo
    (el límite de palabras lo siguen fijando las plantillas). Solo se lee ``message.content``;
    el razonamiento interno nunca llega al estudiante.
    """

    nombre = "groq"

    def __init__(self, api_key: str, modelo: str, cliente=None, respaldo: LLMProvider | None = None):
        self._api_key = (api_key or "").strip()
        self._modelo = modelo
        self._cliente = cliente  # opcional: objeto con .chat.completions.create (pruebas)
        self._respaldo = respaldo or MockLLMProvider()

    def _obtener_cliente(self, tiempo_limite: float):
        if self._cliente is not None:
            return self._cliente
        from groq import Groq  # import perezoso: sin el paquete solo falla esta llamada y se usa el mock

        return Groq(api_key=self._api_key, timeout=tiempo_limite, max_retries=0)

    def generar(self, solicitud: SolicitudLLM) -> RespuestaLLM:
        if not self._api_key:
            log.warning("GROQ_API_KEY vacía: se usa el modo demostración.")
            return self._respaldo.generar(solicitud)
        try:
            cfg = cargar_llm()
            razon = cfg.get("razonamiento", {})
            limite = solicitud.tiempo_limite_seg or cfg["tiempo_limite_seg"]
            esquema = {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "tipo_entregado": {"type": "string", "enum": [solicitud.tipo_ayuda]},
                    "mensaje": {"type": "string"},
                    "codigo_sql": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                },
                "required": ["tipo_entregado", "mensaje", "codigo_sql"],
            }
            respuesta = self._obtener_cliente(limite).chat.completions.create(
                model=self._modelo,
                messages=[
                    {"role": "system", "content": solicitud.prompt_sistema},
                    {"role": "user", "content": solicitud.mensaje_usuario},
                ],
                temperature=cfg["temperatura"],
                max_completion_tokens=cfg["max_tokens"][solicitud.tipo_ayuda] + int(razon.get("margen_tokens", 0)),
                reasoning_effort=razon.get("esfuerzo", "low"),
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "ayuda_adaptativa", "strict": True, "schema": esquema},
                },
                stream=False,
                timeout=limite,
            )
            eleccion = respuesta.choices[0]
            texto = (eleccion.message.content or "").strip()
            if not texto:
                raise ValueError(f"respuesta vacía (finish_reason={eleccion.finish_reason})")
            return RespuestaLLM(texto, self.nombre, es_respaldo=False, etiquetas=(cfg["etiqueta_ia"],))
        except Exception as e:  # noqa: BLE001  (red, HTTP, formato o paquete ausente: nunca llega al estudiante)
            estado = getattr(e, "status_code", None)
            log.warning(
                "Falló la llamada a Groq (%s%s): se usa el modo demostración.",
                type(e).__name__,
                f", HTTP {estado}" if estado else "",
            )
            return self._respaldo.generar(solicitud)


class OpenAIProvider(LLMProvider):
    """Responses API, salida estructurada y sin almacenamiento remoto de la respuesta."""

    nombre = "openai"

    def __init__(self, api_key: str = "", modelo: str = "gpt-6-luna", cliente: httpx.Client | None = None):
        self._api_key = (api_key or "").strip()
        self._modelo = modelo
        self._cliente = cliente

    def generar(self, solicitud: SolicitudLLM) -> RespuestaLLM:
        if not self._api_key:
            return MockLLMProvider().generar(solicitud)
        cfg = cargar_llm()
        esquema = {
            "type": "object", "additionalProperties": False,
            "properties": {
                "tipo_entregado": {"type": "string", "enum": [solicitud.tipo_ayuda]},
                "mensaje": {"type": "string"}, "codigo_sql": {"type": ["string", "null"]},
            }, "required": ["tipo_entregado", "mensaje", "codigo_sql"],
        }
        cliente = self._cliente or httpx.Client()
        try:
            r = cliente.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._modelo, "instructions": solicitud.prompt_sistema,
                    "input": solicitud.mensaje_usuario, "store": False,
                    "reasoning": {"effort": "none"},
                    "max_output_tokens": cfg["max_tokens"][solicitud.tipo_ayuda],
                    "text": {"format": {"type": "json_schema", "name": "ayuda_sql", "strict": True, "schema": esquema}},
                },
                timeout=solicitud.tiempo_limite_seg or cfg["tiempo_limite_seg"],
            )
            r.raise_for_status()
            datos = r.json()
            if datos.get("status") != "completed":
                raise ValueError("respuesta incompleta")
            texto = "".join(
                contenido.get("text", "") for salida in datos.get("output", []) if salida.get("type") == "message"
                for contenido in salida.get("content", []) if contenido.get("type") == "output_text"
            ).strip()
            if not texto:
                raise ValueError("respuesta vacía o rechazada")
            return RespuestaLLM(texto, self.nombre, False, (cfg["etiqueta_ia"],))
        except Exception as exc:
            log.warning("Falló OpenAI (%s): se usa el respaldo.", type(exc).__name__)
            return MockLLMProvider().generar(solicitud)
        finally:
            if self._cliente is None:
                cliente.close()
