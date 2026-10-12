import json
import logging

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.modules.asistencia.config_llm import cargar_llm
from app.modules.asistencia.llm.base import LLMProvider, NoConfigurado, SolicitudLLM
from app.modules.asistencia.llm.fabrica import obtener_proveedor
from app.modules.asistencia.llm.mock import TEXTO_GENERICO, MockLLMProvider
from app.modules.asistencia.llm.proveedores_externos import AnthropicProvider, OpenAIProvider
from app.modules.asistencia.models import SolicitudAyuda, ValoracionAyuda
from app.modules.auth.models import Usuario
from app.modules.desafios.models import Concepto, Desafio, SesionDesafio

RESPALDO = {"mensaje": "Piensa en las condiciones.", "codigo_sql": None}


def solicitud(tipo="AY1", respaldo=RESPALDO):
    return SolicitudLLM(tipo, "SISTEMA", "DATOS", respaldo)


def anthropic(manejador, api_key="clave-falsa", **kw):
    cliente = httpx.Client(transport=httpx.MockTransport(manejador))
    return AnthropicProvider(api_key, "modelo-x", cliente=cliente, **kw)


# ---------- Proveedores ----------
def test_el_contrato_es_abstracto():
    with pytest.raises(TypeError):
        LLMProvider()  # type: ignore[abstract]


def test_mock_devuelve_la_ayuda_de_respaldo_en_json():
    r = MockLLMProvider().generar(solicitud("AY3", {"mensaje": "Completa ___", "codigo_sql": "SELECT ___"}))
    assert r.proveedor == "mock" and r.es_respaldo is True
    assert r.etiquetas == (cargar_llm()["etiqueta_ia"], cargar_llm()["etiqueta_mock"])
    assert json.loads(r.texto) == {"tipo_entregado": "AY3", "mensaje": "Completa ___", "codigo_sql": "SELECT ___"}


def test_mock_sin_respaldo_usa_texto_generico():
    d = json.loads(MockLLMProvider().generar(solicitud("AY2", None)).texto)
    assert d["tipo_entregado"] == "AY2" and d["mensaje"] == TEXTO_GENERICO and d["codigo_sql"] is None


def test_anthropic_envia_el_prompt_y_devuelve_el_texto():
    visto = {}

    def manejador(req: httpx.Request) -> httpx.Response:
        visto["cabeceras"] = req.headers
        visto["cuerpo"] = json.loads(req.content)
        visto["timeout"] = req.extensions["timeout"]
        return httpx.Response(200, json={"content": [{"type": "text", "text": '{"tipo_entregado":"AY1"}'}]})

    r = anthropic(manejador).generar(solicitud())
    assert r.texto == '{"tipo_entregado":"AY1"}' and r.proveedor == "anthropic" and r.es_respaldo is False
    assert r.etiquetas == (cargar_llm()["etiqueta_ia"],)
    assert visto["cabeceras"]["x-api-key"] == "clave-falsa"
    assert visto["cuerpo"]["model"] == "modelo-x" and visto["cuerpo"]["system"] == "SISTEMA"
    assert visto["cuerpo"]["messages"] == [{"role": "user", "content": "DATOS"}]
    cfg = cargar_llm()  # los límites salen de llm.json, no del código
    assert visto["cuerpo"]["max_tokens"] == cfg["max_tokens"]["AY1"]
    assert visto["cuerpo"]["temperature"] == cfg["temperatura"]
    assert visto["timeout"]["read"] == cfg["tiempo_limite_seg"]
    assert "RESPALDO" not in json.dumps(visto["cuerpo"]) and "Piensa" not in json.dumps(visto["cuerpo"])


def test_anthropic_sin_clave_cae_al_mock_sin_llamar_a_la_red():
    llamadas = []
    r = anthropic(lambda req: llamadas.append(req) or httpx.Response(200, json={}), api_key="  ").generar(solicitud())
    assert llamadas == [] and r.proveedor == "mock" and r.es_respaldo is True


@pytest.mark.parametrize(
    "manejador",
    [
        lambda req: httpx.Response(500, json={"error": "x"}),
        lambda req: httpx.Response(429, json={}),
        lambda req: httpx.Response(200, text="no es json"),
        lambda req: httpx.Response(200, json={"content": []}),
        lambda req: (_ for _ in ()).throw(httpx.ReadTimeout("demora")),
        lambda req: (_ for _ in ()).throw(httpx.ConnectError("sin red")),
    ],
)
def test_anthropic_ante_cualquier_fallo_cae_al_mock_sin_error(manejador):
    r = anthropic(manejador).generar(solicitud("AY2"))
    assert r.proveedor == "mock" and r.es_respaldo is True
    assert json.loads(r.texto)["tipo_entregado"] == "AY2"


def test_la_clave_no_se_escribe_en_los_registros(caplog):
    with caplog.at_level(logging.DEBUG):
        anthropic(lambda req: httpx.Response(500), api_key="SECRETO-123").generar(solicitud())
    assert "SECRETO-123" not in caplog.text


def test_openai_solo_tiene_la_firma():
    with pytest.raises(NoConfigurado):
        OpenAIProvider().generar(solicitud())


def test_fabrica_elige_el_proveedor_por_ajuste():
    def cfg(**kw):
        return Settings(_env_file=None, **kw)

    assert isinstance(obtener_proveedor(cfg()), MockLLMProvider)  # por defecto
    assert isinstance(obtener_proveedor(cfg(llm_provider="Anthropic")), AnthropicProvider)
    assert isinstance(obtener_proveedor(cfg(llm_provider="openai")), OpenAIProvider)
    assert isinstance(obtener_proveedor(cfg(llm_provider="otro")), MockLLMProvider)
    assert cfg().llm_provider == "mock" and cfg().anthropic_api_key == ""
    assert not hasattr(cfg(), "llm_timeout_seg") and not hasattr(cfg(), "llm_max_tokens")


# ---------- Modelos ----------
def _base(db):
    u = Usuario(nombre="Ana", correo="ana@uni.edu", hash_password="x", rol="estudiante", activo=True)
    c = db.scalar(select(Concepto))
    d = Desafio(titulo="T", enunciado="E", concepto_id=c.id, dificultad="D1", esquema_sql="s",
                sandbox_setup_sql="s", solucion_referencia="s", tiempo_referencia_seg=120)
    db.add_all([u, d])
    db.commit()
    s = SesionDesafio(usuario_id=u.id, desafio_id=d.id)
    db.add(s)
    db.commit()
    return u, d, s


def test_solicitud_y_valoracion_se_guardan(client, db):
    u, d, s = _base(db)
    sol = SolicitudAyuda(sesion_id=s.id, usuario_id=u.id, desafio_id=d.id, tipo_ayuda="AY1",
                         fue_respaldo=True, proveedor="mock", texto_entregado="Pista")
    db.add(sol)
    db.commit()
    assert sol.momento is not None and sol.codigo_sql is None and sol.incidente_validacion is None
    db.add(ValoracionAyuda(solicitud_id=sol.id, usuario_id=u.id, valor=-1))
    db.commit()
    assert db.scalar(select(ValoracionAyuda.valor)) == -1


def test_restricciones_de_los_modelos(client, db):
    u, d, s = _base(db)
    args = dict(sesion_id=s.id, usuario_id=u.id, desafio_id=d.id, proveedor="mock", texto_entregado="t")
    db.add(SolicitudAyuda(tipo_ayuda="AY9", **args))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    sol = SolicitudAyuda(tipo_ayuda="AY2", **args)
    db.add(sol)
    db.commit()
    db.add(ValoracionAyuda(solicitud_id=sol.id, usuario_id=u.id, valor=0))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add_all([ValoracionAyuda(solicitud_id=sol.id, usuario_id=u.id, valor=1)])
    db.commit()
    db.add(ValoracionAyuda(solicitud_id=sol.id, usuario_id=u.id, valor=-1))
    with pytest.raises(IntegrityError):
        db.commit()
