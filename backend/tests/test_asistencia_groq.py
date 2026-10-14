"""GroqProvider con un cliente simulado (sin red). Verifica los parámetros que se envían y las caídas al mock."""
import json
import logging
from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.modules.asistencia import validador
from app.modules.asistencia.config_llm import cargar_llm
from app.modules.asistencia.llm.base import SolicitudLLM
from app.modules.asistencia.llm.fabrica import obtener_proveedor
from app.modules.asistencia.llm.proveedores_externos import GroqProvider

RESPALDO = {"mensaje": "Piensa en las condiciones.", "codigo_sql": None}
JSON_OK = '{"tipo_entregado":"AY1","mensaje":"¿Qué filtra tu WHERE?","codigo_sql":null}'


def solicitud(tipo="AY1"):
    return SolicitudLLM(tipo, "SISTEMA", "DATOS", RESPALDO)


class ClienteFalso:
    """Imita client.chat.completions.create(...) del SDK de groq."""

    def __init__(self, contenido=JSON_OK, error=None, finish="stop"):
        self.llamadas = []
        self._contenido, self._error, self._finish = contenido, error, finish
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._crear))

    def _crear(self, **kw):
        self.llamadas.append(kw)
        if self._error:
            raise self._error
        msg = SimpleNamespace(content=self._contenido, reasoning="pensando...")
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason=self._finish)])


def groq(cliente, api_key="clave-falsa"):
    return GroqProvider(api_key, "modelo-x", cliente=cliente)


def test_envia_prompt_y_parametros_de_llm_json():
    c = ClienteFalso()
    r = groq(c).generar(solicitud("AY2"))
    assert r.texto == JSON_OK and r.proveedor == "groq" and r.es_respaldo is False
    assert r.etiquetas == (cargar_llm()["etiqueta_ia"],)
    kw = c.llamadas[0]
    cfg = cargar_llm()
    assert kw["model"] == "modelo-x" and kw["stream"] is False
    assert kw["messages"] == [{"role": "system", "content": "SISTEMA"}, {"role": "user", "content": "DATOS"}]
    assert kw["temperature"] == cfg["temperatura"]
    # el razonamiento de gpt-oss gasta tokens: se suma el margen configurado al tope del tipo
    assert kw["max_completion_tokens"] == cfg["max_tokens"]["AY2"] + cfg["razonamiento"]["margen_tokens"]
    assert kw["reasoning_effort"] == cfg["razonamiento"]["esfuerzo"]
    assert kw["timeout"] == cfg["tiempo_limite_seg"]
    assert "Piensa" not in json.dumps(kw)  # el respaldo del desafío no se envía al LLM


def test_la_respuesta_pasa_el_validador():
    r = groq(ClienteFalso()).generar(solicitud("AY1"))
    assert validador.validar(r.texto, "AY1").ok


def test_sin_clave_cae_al_mock_sin_llamar_al_cliente():
    c = ClienteFalso()
    r = groq(c, api_key="  ").generar(solicitud())
    assert c.llamadas == [] and r.proveedor == "mock" and r.es_respaldo is True


@pytest.mark.parametrize(
    "cliente",
    [
        ClienteFalso(error=RuntimeError("429")),
        ClienteFalso(error=TimeoutError("demora")),
        ClienteFalso(contenido=""),
        ClienteFalso(contenido=None, finish="length"),  # el razonamiento se comió los tokens
    ],
)
def test_ante_cualquier_fallo_cae_al_mock_sin_error(cliente):
    r = groq(cliente).generar(solicitud("AY3"))
    assert r.proveedor == "mock" and r.es_respaldo is True
    assert json.loads(r.texto)["tipo_entregado"] == "AY3"


def test_sin_el_paquete_groq_cae_al_mock(monkeypatch):
    import builtins

    real = builtins.__import__

    def sin_groq(nombre, *a, **kw):
        if nombre == "groq":
            raise ImportError("no instalado")
        return real(nombre, *a, **kw)

    monkeypatch.setattr(builtins, "__import__", sin_groq)
    r = GroqProvider("clave-falsa", "modelo-x").generar(solicitud())
    assert r.proveedor == "mock"


def test_la_clave_no_se_escribe_en_los_registros(caplog):
    with caplog.at_level(logging.DEBUG):
        groq(ClienteFalso(error=RuntimeError("fallo")), api_key="SECRETO-123").generar(solicitud())
    assert "SECRETO-123" not in caplog.text


def test_fabrica_elige_groq_y_lee_sus_ajustes():
    cfg = Settings(_env_file=None, llm_provider="Groq", groq_api_key="k", groq_model="m")
    p = obtener_proveedor(cfg)
    assert isinstance(p, GroqProvider) and p._modelo == "m" and p._api_key == "k"
    assert Settings(_env_file=None).groq_model == "openai/gpt-oss-120b"


def test_la_clave_tambien_se_lee_de_la_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "desde-entorno")
    assert Settings(_env_file=None).groq_api_key == "desde-entorno"
