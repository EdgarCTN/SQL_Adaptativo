import json

import pytest
from sqlalchemy import select

from app.modules.analitica import servicio
from app.modules.analitica.models import IndicadorHistorico
from app.modules.analitica.seudonimizar import id_pseudonimo
from app.modules.desafios.models import Desafio
from app.modules.motor_retiro import motor
from conftest import API, cabecera, registrar, token_de
from test_desafios import crear_desafio
from test_motor_integracion import abandonar, ana, concepto, estado, poner_ns, preparar, primera_ayuda, resolver


@pytest.fixture(autouse=True)
def _sin_sembrados(client, db):
    db.execute(Desafio.__table__.delete())
    db.commit()


def filas(db):
    db.expire_all()
    return list(db.scalars(select(IndicadorHistorico).order_by(IndicadorHistorico.id)))


def test_cada_cierre_escribe_una_fila_y_el_nivel_se_sigue_ajustando(client, db):
    h, did = preparar(client, db)
    for _ in range(2):
        assert abandonar(client, h, did)["ajuste_nivel"] is None
    j = abandonar(client, h, did)
    assert j["ajuste_nivel"]["ns_anterior"] == 1 and j["ajuste_nivel"]["ns_nuevo"] == 2  # R5 como antes
    rs = filas(db)
    assert len(rs) == 3 and len({r.sesion_id for r in rs}) == 3
    assert [r.ns for r in rs] == [1, 1, 2] and [r.n_ventana for r in rs] == [1, 2, 3]
    assert all(r.usuario_id == ana(db).id and r.concepto_id == concepto(db).id and r.ta == 0.0 and r.ua == 0.0 for r in rs)
    assert estado(db).ns == 2


def test_la_fila_registra_ua_cuando_pidio_ayuda_y_tr_cuando_hay_tiempo(client, db):
    h, did = preparar(client, db)
    primera_ayuda(client, h, did)  # pide ayuda y abandona
    assert filas(db)[-1].ua == 1.0
    poner_ns(db, 2)  # fija un cambio de NS: la ventana se reinicia y deja fuera el desafío anterior
    resolver(client, h, did)
    ultima = filas(db)[-1]
    assert ultima.n_ventana == 1 and ultima.ua == 0.0 and ultima.ta == 1.0 and ultima.tr is not None


def test_retiro_r1_guarda_el_ns_resultante(client, db):
    h, did = preparar(client, db)
    poner_ns(db, 2)
    for _ in range(3):
        resolver(client, h, did)
    rs = filas(db)
    assert [r.ns for r in rs] == [2, 2, 1] and rs[-1].ta == 1.0


def test_un_fallo_al_guardar_el_historico_no_rompe_el_cierre_ni_el_ajuste(client, db, monkeypatch):
    def falla(*a, **k):
        raise RuntimeError("fallo simulado")

    monkeypatch.setattr(motor, "registrar_historico", falla)
    h, did = preparar(client, db)
    abandonar(client, h, did)
    abandonar(client, h, did)
    j = abandonar(client, h, did)
    assert j["ajuste_nivel"]["ns_nuevo"] == 2 and estado(db).ns == 2
    assert filas(db) == []


def test_servicio_indicadores_ventana_y_serie_historica(client, db):
    h, did = preparar(client, db)
    abandonar(client, h, did)
    primera_ayuda(client, h, did)
    uid, cid = ana(db).id, concepto(db).id
    ind = servicio.indicadores_ventana(db, uid, cid)
    assert ind == {"n": 2, "ta": 0.0, "ni": 0.0, "tr": ind["tr"], "ua": 0.5, "desafios_desde_cambio": 2}
    serie = servicio.serie_historica(db, uid)
    assert [f["ns"] for f in serie] == [1, 1] and serie[0]["concepto_codigo"] == "filtrado" and isinstance(serie[0]["creado_en"], str)
    assert servicio.serie_historica(db, uid, cid) == serie and servicio.serie_historica(db, uid, cid + 999) == []
    json.dumps(serie)  # serializable


def test_agregados_solo_con_seudonimos(client, db):
    h, did = preparar(client, db)
    for _ in range(3):
        abandonar(client, h, did)
    registrar(client, nombre="Beto Ruiz", correo="beto@uni.edu")
    hb = cabecera(token_de(client, "beto@uni.edu"))
    abandonar(client, hb, did)
    ag = servicio.agregados(db)
    texto = json.dumps(ag, ensure_ascii=False)
    assert "Ana" not in texto and "Beto" not in texto and "uni.edu" not in texto and "usuario_id" not in texto
    assert {e["id_pseudonimo"] for e in ag["por_estudiante"]} == {id_pseudonimo(ana(db).id), id_pseudonimo(ana(db).id + 1)}
    pc = ag["por_concepto"][0]
    assert pc["concepto_codigo"] == "filtrado" and pc["n_estudiantes"] == 2 and pc["n_cierres"] == 4
    assert pc["distribucion_ns"] == {"0": 0, "1": 1, "2": 1, "3": 0}
    assert servicio.agregados(db, concepto_id=concepto(db).id + 999) == {"por_concepto": [], "por_estudiante": []}
