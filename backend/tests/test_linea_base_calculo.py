import copy
import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.reglas import RUTA_REGLAS, leer_reglas
from app.modules.desafios.models import Concepto
from app.modules.linea_base import service
from app.modules.linea_base.calculo import ajustar_por_3_1, calcular_linea_base, ns_desde_m
from app.modules.linea_base.models import (
    LineaBaseCuestionario,
    LineaBaseRespuesta,
    LineaBaseResultado,
    NivelSoporte,
    Omision,
)
from app.modules.linea_base.schemas import RespuestaIn
from app.modules.linea_base.service import indexar_preguntas
from app.modules.motor_retiro.niveles import NS_POR_DEFECTO, NivelSoporteService
from app.seeds.seed import RUTA_CUESTIONARIO
from conftest import API, cabecera, registrar, token_de

LB = f"{API}/linea-base"
CONTENIDO = json.loads(Path(RUTA_CUESTIONARIO).read_text(encoding="utf-8-sig"))
INDICE = indexar_preguntas(CONTENIDO)
REGLAS = leer_reglas(RUTA_REGLAS)
CONCEPTOS = [
    "filtrado", "ordenamiento", "conteo_agregacion", "join", "group_by",
    "having", "left_join", "subconsulta", "join_agregacion", "funciones_ventana",
]
P2 = [i for i in INDICE if i.tipo == "prueba"]
CORRECTA = {i.id: i.correcta for i in P2}
INCORRECTA = {i.id: next(o for o in "abcd" if o != i.correcta) for i in P2}

PART1 = {"1.1": ["a"], "1.2": ["a"], "1.3": ["a"], "1.4": ["a"], "1.5": ["b"], "1.6": ["a"]}
PART3 = {"3.1": "b", "3.2": "b", "3.3": "a", "3.4": "a", "3.5": "a", "3.6": "b"}


def armar(p2=None, base="ok5", part1=None, part3=None) -> dict:
    """Respuestas completas. p2: {pregunta: ('ok'|'mal', conf) | 'no_se' | 'muy_facil' | 'muy_dificil'}."""
    p2 = p2 or {}
    resp = {}
    for pid, op in {**PART1, **(part1 or {})}.items():
        resp[pid] = RespuestaIn(pregunta_id=pid, opciones=op)
    for pid, op in {**PART3, **(part3 or {})}.items():
        resp[pid] = RespuestaIn(pregunta_id=pid, opciones=[op])
    for i in P2:
        v = p2.get(i.id, base)
        if v == "ok5":
            r = RespuestaIn(pregunta_id=i.id, opciones=[CORRECTA[i.id]], confianza=5)
        elif v == "no_se":
            r = RespuestaIn(pregunta_id=i.id, opciones=["e"])
        elif v in ("muy_facil", "muy_dificil"):
            r = RespuestaIn(pregunta_id=i.id, omitir=v)
        else:
            tipo, conf = v
            opcion = CORRECTA[i.id] if tipo == "ok" else INCORRECTA[i.id]
            r = RespuestaIn(pregunta_id=i.id, opciones=[opcion], confianza=conf)
        resp[i.id] = r
    return resp


def calcular(resp, conceptos=None, reglas=None):
    return calcular_linea_base(INDICE, resp, conceptos or CONCEPTOS, reglas or REGLAS)


# ---------- calificación y m ----------
def test_clave_de_correccion_es_opcion_3_para_p1_p3_y_4_para_p4_p11():
    esperado = {**{f"P{n}": "c" for n in (1, 2, 3)}, **{f"P{n}": "d" for n in range(4, 12)}}
    assert CORRECTA == esperado


@pytest.mark.parametrize("conf,acierto,error", [(5, 0.975, 0.025), (4, 0.875, 0.125), (3, 0.725, 0.275), (2, 0.6, 0.4), (1, 0.5, 0.5)])
def test_m_por_item_segun_tabla_15(conf, acierto, error):
    r = calcular(armar({"P1": ("ok", conf), "P2": ("mal", conf)}))
    assert r.m_por_item["P1"]["m"] == pytest.approx(acierto) and r.m_por_item["P1"]["resultado"] == "acierto"
    assert r.m_por_item["P2"]["m"] == pytest.approx(error) and r.m_por_item["P2"]["resultado"] == "error"


def test_no_se_vale_025_sin_importar_confianza():
    r = calcular(armar({"P1": "no_se"}))
    assert r.m_por_item["P1"] == {"m": 0.25, "resultado": "no_se", "confianza": None, "concepto": "filtrado", "nivel": 1}


def test_omisiones_valen_0975_y_0025():
    r = calcular(armar({"P1": "muy_facil", "P2": "muy_dificil"}))
    assert r.m_por_item["P1"]["m"] == 0.975 and r.m_por_item["P1"]["resultado"] == "omision_muy_facil"
    assert r.m_por_item["P2"]["m"] == 0.025 and r.m_por_item["P2"]["resultado"] == "omision_muy_dificil"


# ---------- NS inicial (R0) ----------
def test_todo_correcto_con_confianza_5_da_ns0_en_todo():
    r = calcular(armar())
    assert set(r.ns_inicial) == set(CONCEPTOS) and set(r.ns_inicial.values()) == {0}
    assert r.m_global == 0.975 and all(x["m"] == 0.975 for x in r.m_por_item.values())


def test_todo_no_se_da_m_025_y_ns2():
    r = calcular(armar(base="no_se"))
    assert r.m_global == 0.25 and set(r.ns_inicial.values()) == {2}
    assert all(c["m"] == 0.25 for c in r.m_por_concepto.values())


def test_cortes_ns_en_los_limites():
    assert ns_desde_m(0.70, REGLAS["cortes_linea_base"]) == 0
    assert ns_desde_m(0.6999, REGLAS["cortes_linea_base"]) == 1
    assert ns_desde_m(0.40, REGLAS["cortes_linea_base"]) == 1
    assert ns_desde_m(0.3999, REGLAS["cortes_linea_base"]) == 2
    r = calcular(armar({"P2": ("mal", 2), "P3": ("mal", 3), "P5": ("ok", 3)}))
    assert r.ns_inicial["ordenamiento"] == 1  # m = 0.400 exacto
    assert r.ns_inicial["conteo_agregacion"] == 2  # m = 0.275
    assert r.ns_inicial["join"] == 0  # m = 0.725


def test_promedio_por_concepto_con_varios_items():
    r = calcular(armar({"P1": ("ok", 5), "P4": ("mal", 5)}))  # filtrado: (0.975 + 0.025) / 2
    assert r.m_por_concepto["filtrado"]["m"] == pytest.approx(0.5)
    assert r.m_por_concepto["filtrado"]["n_items"] == 2 and r.ns_inicial["filtrado"] == 1


def test_todos_los_items_de_un_concepto_en_muy_facil_da_ns1():
    r = calcular(armar({"P1": "muy_facil", "P4": "muy_facil"}))  # filtrado tiene P1 y P4
    assert r.m_por_concepto["filtrado"]["m"] == 0.975 and r.m_por_concepto["filtrado"]["todas_muy_facil"] is True
    assert r.ns_inicial["filtrado"] == 1
    assert r.ns_inicial["ordenamiento"] == 0


def test_muy_facil_parcial_no_activa_la_excepcion():
    r = calcular(armar({"P1": "muy_facil"}))  # P4 sigue acertado con confianza 5
    assert r.m_por_concepto["filtrado"]["todas_muy_facil"] is False and r.ns_inicial["filtrado"] == 0


def test_concepto_sin_items_usa_el_promedio_global():
    p2 = {f"P{n}": "no_se" for n in range(7, 12)}  # P1-P6 acertados con 5; P7-P11 «No sé»
    r = calcular(armar(p2), conceptos=CONCEPTOS + ["sintetico"])
    esperado = (6 * 0.975 + 5 * 0.25) / 11
    assert r.m_global == pytest.approx(esperado, abs=1e-6)
    sint = r.m_por_concepto["sintetico"]
    assert sint["origen"] == "global" and sint["n_items"] == 0 and sint["m"] == r.m_global
    assert r.ns_inicial["sintetico"] == 1  # 0.6455 → NS1
    assert r.ns_inicial["filtrado"] == 0 and r.ns_inicial["having"] == 2


def test_los_valores_salen_de_reglas_json():
    otras = copy.deepcopy(REGLAS)
    otras["cortes_linea_base"]["ns0_m_minimo"] = 0.99  # 0.975 ya no alcanza NS0
    assert set(calcular(armar(), reglas=otras).ns_inicial.values()) == {1}
    otras = copy.deepcopy(REGLAS)
    otras["valor_dominio_m"]["no_se"] = 0.9
    assert calcular(armar({"P1": "no_se"}), reglas=otras).m_por_item["P1"]["m"] == 0.9


# ---------- se guardan pero no se aplican ----------
def test_dificultad_inicial():
    d1 = {f"P{n}": ("mal", 5) for n in (1, 2, 3, 4)}
    d2 = {f"P{n}": ("mal", 5) for n in (5, 6, 7, 8)}
    d3 = {f"P{n}": ("mal", 5) for n in (9, 10, 11)}
    assert calcular(armar(d1)).dificultad_inicial == "D1"
    assert calcular(armar(d2)).dificultad_inicial == "D2"
    assert calcular(armar(d3)).dificultad_inicial == "D3"
    assert calcular(armar()).dificultad_inicial == "D3"
    r = calcular(armar({**d1, **d2}))
    assert r.dificultad_inicial == "D1" and set(r.m_por_nivel) == {"D1", "D2", "D3"}
    assert r.m_por_nivel["D1"] == 0.025 and r.m_por_nivel["D3"] == 0.975


def test_dificultad_inicial_no_cambia_el_ns():
    r = calcular(armar({f"P{n}": ("mal", 5) for n in (1, 2, 3, 4)}))
    assert r.dificultad_inicial == "D1"
    assert r.ns_inicial["filtrado"] == 2 and r.ns_inicial["join"] == 0


@pytest.mark.parametrize(
    "ns,pref,esperado",
    [(1, "AY1", 1), (2, "AY1", 1), (1, "AY2", 1), (2, "AY2", 2), (1, "AY3", 2), (1, "AY4", 2),
     (2, "AY3", 2), (2, "AY4", 2), (0, "AY1", 0), (0, "AY3", 0), (0, "AY4", 0)],
)
def test_ajuste_por_preferencia_3_1(ns, pref, esperado):
    assert ajustar_por_3_1(ns, pref) == esperado


def test_ajuste_3_1_se_guarda_y_no_se_aplica():
    p2 = {"P2": ("mal", 2), "P3": "no_se", "P1": "muy_facil", "P4": "muy_facil"}
    r = calcular(armar(p2, part3={"3.1": "c"}))  # preferencia AY3 «solución parcial»
    assert r.ns_inicial["ordenamiento"] == 1 and r.ajuste_3_1["ordenamiento"] == 2
    assert r.ns_inicial["conteo_agregacion"] == 2 and r.ajuste_3_1["conteo_agregacion"] == 2
    assert r.ns_inicial["filtrado"] == 1 and r.ajuste_3_1["filtrado"] == 1  # excepción «Muy fácil»
    assert r.ns_inicial["join"] == 0 and r.ajuste_3_1["join"] == 0
    assert r.banderas["ajuste_ns_3_1"] == r.ajuste_3_1
    r = calcular(armar(p2, part3={"3.1": "a"}))  # AY1 «pista general»
    assert r.ajuste_3_1["conteo_agregacion"] == 1 and r.ns_inicial["conteo_agregacion"] == 2


@pytest.mark.parametrize(
    "part1,part3,riesgo,cuantas",
    [
        ({}, {}, False, 0),
        ({"1.6": ["c"]}, {}, False, 1),
        ({"1.6": ["c"]}, {"3.2": "a"}, True, 2),
        ({"1.6": ["d"]}, {"3.6": "a"}, True, 2),
        ({"1.6": ["b"]}, {"3.2": "a", "3.6": "a"}, True, 2),
        ({"1.6": ["d"]}, {"3.2": "a", "3.6": "a"}, True, 3),
        ({"1.6": ["a"]}, {"3.2": "a"}, False, 1),
    ],
)
def test_bandera_r9(part1, part3, riesgo, cuantas):
    r9 = calcular(armar(part1=part1, part3=part3)).banderas["r9"]
    assert r9["riesgo"] is riesgo and r9["senales_cumplidas"] == cuantas


def test_bandera_r11_cuenta_errores_con_confianza_alta():
    r11 = calcular(armar({"P1": ("mal", 5), "P2": ("mal", 4)})).banderas["r11"]
    assert r11 == {"errores_confianza_alta": 2, "sobreconfianza": True}
    assert calcular(armar({"P1": ("mal", 5)})).banderas["r11"] == {"errores_confianza_alta": 1, "sobreconfianza": False}
    # no cuentan: error con confianza 3, «No sé», omisiones ni aciertos seguros
    sin = calcular(armar({"P1": ("mal", 3), "P2": "no_se", "P3": "muy_dificil", "P4": "muy_facil", "P5": ("mal", 2)}))
    assert sin.banderas["r11"] == {"errores_confianza_alta": 0, "sobreconfianza": False}


def test_preferencias_contexto_y_tono_se_guardan_crudos():
    r = calcular(armar(part1={"1.2": ["a", "c"], "1.5": ["d"]}, part3={"3.1": "d", "3.2": "c", "3.3": "b", "3.4": "d", "3.5": "c", "3.6": "d"}))
    assert r.preferencias == {"3.1": "AY4", "3.2": "2_3", "3.3": "ofrecer", "3.4": "mantener", "3.5": "reflexivo", "3.6": "no_ver"}
    assert r.contexto == {"1.1": ["a"], "1.2": ["a", "c"], "1.3": ["a"], "1.4": ["a"], "1.5": ["d"], "1.6": ["a"]}


# ---------- integración con la API y la BD ----------
def _enviar_completo(client, db, p2=None, **kw):
    """Registra al estudiante, consiente y envía respuestas armadas con la clave guardada en la BD."""
    registrar(client)
    h = cabecera(token_de(client))
    client.post(f"{LB}/consentimiento", json={"acepta": True}, headers=h)
    cid = client.get(f"{LB}/cuestionario", headers=h).json()["id"]
    resp = armar(p2, **kw)
    cuerpo = {
        "cuestionario_id": cid,
        "respuestas": [r.model_dump(exclude_none=True) | {"opciones": r.opciones} for r in resp.values()],
    }
    return client.post(f"{LB}/respuestas", json=cuerpo, headers=h), h


def _ns_por_codigo(db) -> dict:
    filas = db.execute(select(Concepto.codigo, NivelSoporte.ns).join(NivelSoporte, NivelSoporte.concepto_id == Concepto.id))
    return dict(filas.all())


def test_api_todo_correcto_guarda_ns0_y_el_resultado(client, db):
    r, _ = _enviar_completo(client, db)
    assert r.status_code == 200, r.text
    assert "nivel inicial" in r.json()["mensaje"]
    assert _ns_por_codigo(db) == {c: 0 for c in CONCEPTOS}
    assert set(db.scalars(select(NivelSoporte.ns_maximo_historico))) == {0}
    res = db.scalar(select(LineaBaseResultado))
    assert res.m_global == 0.975 and res.dificultad_inicial == "D3" and res.reglas_version == REGLAS["version"]
    assert res.ns_inicial_por_concepto == {c: 0 for c in CONCEPTOS}
    assert res.banderas_iniciales["r9"]["riesgo"] is False and res.banderas_iniciales["r11"]["sobreconfianza"] is False
    assert res.preferencias["3.5"] == "directo" and res.contexto["1.5"] == ["b"]
    assert res.m_por_item["P1"]["m"] == 0.975 and res.m_por_nivel["D2"] == 0.975
    # datos crudos conservados
    assert db.scalar(select(func.count()).select_from(LineaBaseRespuesta)) == 23


def test_api_todo_no_se_da_ns2(client, db):
    r, _ = _enviar_completo(client, db, base="no_se")
    assert r.status_code == 200, r.text
    assert set(_ns_por_codigo(db).values()) == {2}
    assert db.scalar(select(LineaBaseResultado.m_global)) == 0.25
    fila = db.scalar(select(LineaBaseRespuesta).where(LineaBaseRespuesta.pregunta_id == "P1"))
    assert fila.es_no_se is True and fila.confianza is None


def test_api_concepto_sin_items_en_la_bd_usa_el_global(client, db):
    db.add(Concepto(codigo="sintetico", nombre="Concepto sintético"))
    db.commit()
    p2 = {f"P{n}": "no_se" for n in range(7, 12)}
    r, _ = _enviar_completo(client, db, p2)
    assert r.status_code == 200, r.text
    ns = _ns_por_codigo(db)
    assert len(ns) == 11 and ns["sintetico"] == 1 and ns["filtrado"] == 0 and ns["having"] == 2
    res = db.scalar(select(LineaBaseResultado))
    assert res.m_por_concepto["sintetico"]["origen"] == "global"


def test_api_todos_muy_facil_de_un_concepto_y_omisiones_guardadas(client, db):
    r, _ = _enviar_completo(client, db, {"P1": "muy_facil", "P4": "muy_facil", "P9": "muy_dificil"})
    assert r.status_code == 200, r.text
    ns = _ns_por_codigo(db)
    assert ns["filtrado"] == 1 and ns["ordenamiento"] == 0 and ns["subconsulta"] == 2  # P9: m 0.025
    assert db.scalar(select(func.count()).select_from(Omision)) == 3


def test_api_los_cortes_se_leen_de_reglas(client, db, monkeypatch):
    otras = copy.deepcopy(REGLAS)
    otras["cortes_linea_base"]["ns0_m_minimo"] = 0.99
    monkeypatch.setattr(service, "cargar_reglas", lambda: otras)
    r, _ = _enviar_completo(client, db)
    assert r.status_code == 200 and set(_ns_por_codigo(db).values()) == {1}


def test_api_reglas_ilegibles_no_guardan_nada(client, db, monkeypatch):
    def falla():
        raise OSError("sin archivo")

    monkeypatch.setattr(service, "cargar_reglas", falla)
    r, _ = _enviar_completo(client, db)
    assert r.status_code == 503 and r.json()["error"] is True and "sin archivo" not in r.text
    assert db.scalar(select(func.count()).select_from(NivelSoporte)) == 0
    assert db.scalar(select(func.count()).select_from(LineaBaseResultado)) == 0
    assert db.scalar(select(func.count()).select_from(LineaBaseRespuesta)) == 0


def test_clave_correcta_de_la_bd_coincide_con_el_json(client, db):
    c = db.scalar(select(LineaBaseCuestionario))
    assert {i.id: i.correcta for i in indexar_preguntas(c.contenido) if i.tipo == "prueba"} == CORRECTA


# ---------- NivelSoporteService ----------
def test_nivel_soporte_service_lee_lo_guardado(client, db):
    r, _ = _enviar_completo(client, db, {"P2": "no_se", "P3": ("mal", 2)})
    assert r.status_code == 200
    from app.modules.auth.models import Usuario

    uid = db.scalar(select(Usuario.id).where(Usuario.correo == "ana@uni.edu"))
    ids = dict(db.execute(select(Concepto.codigo, Concepto.id)).all())
    servicio = NivelSoporteService(db)
    assert servicio.obtener(uid, ids["filtrado"]) == 0
    assert servicio.obtener(uid, ids["ordenamiento"]) == 2
    assert servicio.obtener(uid, ids["conteo_agregacion"]) == 1
    assert NivelSoporteService().obtener(uid, ids["ordenamiento"]) == 2  # abre su propia sesión


def test_nivel_soporte_service_sin_registro_devuelve_1(client, db):
    assert NS_POR_DEFECTO == 1
    assert NivelSoporteService(db).obtener(999, 999) == 1
    assert NivelSoporteService().obtener(999, 999) == 1
