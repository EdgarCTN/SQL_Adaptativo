import json

import pytest

from app.modules.asistencia import validador
from app.modules.asistencia.validador import ContextoValidacion, validar


def js(**kw):
    base = {"tipo_entregado": "AY1", "mensaje": "Piensa en las condiciones.", "codigo_sql": None}
    base.update(kw)
    return json.dumps(base, ensure_ascii=False)


def test_respuesta_valida():
    r = validar(js(), "AY1")
    assert r.ok and r.datos["mensaje"] and r.motivo is None
    assert validar(js(tipo_entregado="AY3", codigo_sql="SELECT ___"), "AY3").ok


def test_tolera_cerca_de_codigo():
    assert validar("```json\n" + js() + "\n```", "AY1").ok


@pytest.mark.parametrize(
    "texto",
    [
        "", "hola", "{no es json", "[1, 2]", '"texto"', "null",
        json.dumps({"tipo_entregado": "AY1", "mensaje": "x"}),  # falta codigo_sql
        json.dumps({"mensaje": "x", "codigo_sql": None}),
        js(mensaje=""), js(mensaje="   "), js(mensaje=5), js(tipo_entregado=1), js(codigo_sql=3),
    ],
)
def test_v1_rechaza_json_incompleto_o_inutilizable(texto):
    r = validar(texto, "AY1")
    assert not r.ok and r.motivo.startswith("V1")


def test_v2_el_tipo_entregado_debe_ser_el_pedido():
    r = validar(js(tipo_entregado="AY4"), "AY2")
    assert not r.ok and r.motivo.startswith("V2") and "AY4" in r.motivo and "AY2" in r.motivo


def test_estructura_lista_para_sumar_validaciones(monkeypatch):
    def v3(ctx: ContextoValidacion):
        return "V3: demasiado largo" if len(ctx.datos["mensaje"]) > 10 else None

    monkeypatch.setattr(validador, "VALIDACIONES", [*validador.VALIDACIONES, v3])
    assert validar(js(mensaje="corto"), "AY1").ok
    r = validar(js(mensaje="x" * 50), "AY1")
    assert not r.ok and r.motivo.startswith("V3")
