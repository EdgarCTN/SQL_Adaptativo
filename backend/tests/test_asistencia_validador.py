import json

import pytest

from app.modules.asistencia import validador
from app.modules.asistencia.validador import ContextoValidacion, validar
from app.modules.desafios.seeds import DESAFIOS


def js(**kw):
    base = {"tipo_entregado": "AY1", "mensaje": "Piensa en las condiciones.", "codigo_sql": None}
    base.update(kw)
    return json.dumps(base, ensure_ascii=False)


def test_respuesta_valida():
    r = validar(js(), "AY1")
    assert r.ok and r.datos["mensaje"] and r.motivo is None
    assert validar(js(tipo_entregado="AY3", codigo_sql="SELECT ___ FROM ___"), "AY3").ok


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
    r = validar(js(mensaje="Esta oración tiene suficientes palabras y sigue en español."), "AY1")
    assert not r.ok and r.motivo.startswith("V3")


def test_v3_ay1_no_entrega_sql_clausulas_ni_solucion():
    contexto = {"solucion": "SELECT titulo FROM libros WHERE anio > 2020;"}
    assert validar(js(), "AY1", **contexto).ok
    for datos in (
        {"codigo_sql": "SELECT * FROM libros", "mensaje": "Piensa en las condiciones."},
        {"codigo_sql": None, "mensaje": "Usa SELECT para elegir las columnas."},
        {"codigo_sql": None, "mensaje": "La respuesta SELECT titulo FROM libros WHERE anio > 2020;"},
    ):
        r = validar(js(**datos), "AY1", **contexto)
        assert not r.ok and r.motivo.startswith("V3")


def test_v4_ay2_rechaza_tablas_columnas_del_desafio_y_sql_invalido():
    contexto = {
        "esquema": "CREATE TABLE libros (titulo TEXT, anio INTEGER);",
        "setup": "CREATE TABLE libros (titulo TEXT, anio INTEGER);",
    }
    ajena = js(tipo_entregado="AY2", mensaje="Observa este ejemplo en otro contexto con cuidado.",
               codigo_sql="SELECT placa FROM autos;")
    assert validar(ajena, "AY2", **contexto).ok
    for codigo in ("SELECT titulo FROM revistas;", "SELECT x FROM libros;", "SELECT FROM;"):
        r = validar(js(tipo_entregado="AY2", mensaje="Observa este ejemplo en otro contexto con cuidado.",
                       codigo_sql=codigo), "AY2", **contexto)
        assert not r.ok and r.motivo.startswith("V4")


def test_v5_ay3_exige_huecos_y_conserva_fragmentos_en_orden():
    solucion = "SELECT titulo, anio FROM libros WHERE anio > 2020;"
    contexto = {"solucion": solucion}
    valida = js(tipo_entregado="AY3", mensaje="Completa los espacios que faltan en esta consulta.",
                codigo_sql="SELECT titulo, ___ FROM libros WHERE ___ > 2020;")
    assert validar(valida, "AY3", **contexto).ok
    invalida = js(tipo_entregado="AY3", mensaje="Completa los espacios que faltan en esta consulta.",
                  codigo_sql="SELECT anio, ___ FROM libros WHERE ___ > 2020;")
    r = validar(invalida, "AY3", **contexto)
    assert not r.ok and r.motivo.startswith("V5")


def test_v6_ejecuta_ay4_y_compara_con_solucion():
    setup = "CREATE TABLE libros (titulo TEXT); INSERT INTO libros VALUES ('A'), ('B');"
    contexto = {"setup": setup, "solucion": "SELECT titulo FROM libros ORDER BY titulo;"}
    cuerpo = {"tipo_entregado": "AY4", "mensaje": "La consulta selecciona todos los títulos ordenados.",
              "codigo_sql": contexto["solucion"]}
    assert validar(json.dumps(cuerpo), "AY4", **contexto).ok
    cuerpo["codigo_sql"] = "SELECT titulo FROM libros WHERE titulo = 'A';"
    r = validar(json.dumps(cuerpo), "AY4", **contexto)
    assert not r.ok and r.motivo.startswith("V6")


def test_v7_v8_y_v9_aplican_idioma_privacidad_y_plazo(monkeypatch):
    assert validar(js(mensaje="Please check every condition before sending your answer."), "AY1").motivo.startswith("V7")
    assert validar(js(), "AY1", personales=("Ana Pérez",)).ok
    for texto in (
        "El nivel de soporte es privado para esta persona.",
        "Contacta a ana@uni.edu para recibir ayuda.",
        "La regla R9 modifica el resultado.",
        "Consulta https://ejemplo.edu para más información.",
        "Ana Pérez puede continuar con la consulta.",
    ):
        r = validar(js(mensaje=texto), "AY1", personales=("Ana Pérez",))
        assert not r.ok and r.motivo.startswith("V8")
    r = validar("esto no es JSON", "AY1", segundos=8.01, limite_seg=8)
    assert not r.ok and r.motivo.startswith("V9")


@pytest.mark.parametrize(
    "desafio,tipo,ayuda",
    [(d, tipo, ayuda) for d in DESAFIOS for tipo, ayuda in d["ayudas"].items()],
    ids=[f"{d['titulo']} {tipo}" for d in DESAFIOS for tipo in d["ayudas"]],
)
def test_las_ayudas_de_respaldo_de_todos_los_desafios_pasan_los_controles(desafio, tipo, ayuda):
    cuerpo = {"tipo_entregado": tipo, "mensaje": ayuda["mensaje"], "codigo_sql": ayuda["codigo_sql"]}
    r = validar(
        json.dumps(cuerpo, ensure_ascii=False), tipo, solucion=desafio["solucion"],
        esquema=desafio["esquema"], setup=desafio["esquema"] + "\n" + desafio["datos"],
    )
    assert r.ok, f"{desafio['titulo']} {tipo}: {r.motivo}"
