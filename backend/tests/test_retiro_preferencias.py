"""Entrega 7: ajuste R0 por la pregunta 3.1, dificultad inicial en el listado y R13 (pregunta 3.4) sobre R1 y R2."""
import pytest
from sqlalchemy import select

from app.modules.asistencia.config_llm import cargar_mensajes_fijos
from app.modules.desafios.models import Desafio
from app.modules.linea_base.calculo import aplicar_ajuste_3_1
from app.modules.linea_base.models import LineaBaseCuestionario, LineaBaseResultado, NivelSoporte
from app.modules.motor_retiro.models import AjustePendiente, EventoMotor, HistorialNivel
from conftest import API, cabecera, registrar, token_de
from test_desafios import crear_desafio
from test_linea_base_calculo import CONCEPTOS, _enviar_completo, _ns_por_codigo
from test_motor_integracion import abandonar, ana, concepto, estado, poner_ns, resolver, resolver_con_error

MENSAJES = cargar_mensajes_fijos()["mensajes"]
NOMBRE = "Filtrado (WHERE)"


@pytest.fixture(autouse=True)
def _sin_sembrados(client, db):
    db.execute(Desafio.__table__.delete())
    db.commit()


# ---------- R0: ajuste por 3.1 (tabla pura) ----------
# (nombre, ns por m, preferencia, todas «Muy fácil», riesgo R9, ns final, motivo)
CASOS_3_1 = [
    ("pista general baja NS2 a 1", 2, "AY1", False, False, 1, "aplicado"),
    ("pista general deja NS1", 1, "AY1", False, False, 1, "sin_cambio"),
    ("ejemplo guiado no cambia NS1", 1, "AY2", False, False, 1, "sin_cambio"),
    ("ejemplo guiado no cambia NS2", 2, "AY2", False, False, 2, "sin_cambio"),
    ("solución parcial sube NS1 a 2", 1, "AY3", False, False, 2, "aplicado"),
    ("solución completa sube NS1 a 2", 1, "AY4", False, False, 2, "aplicado"),
    ("solución parcial deja NS2", 2, "AY3", False, False, 2, "sin_cambio"),
    ("NS0 nunca se toca (pista)", 0, "AY1", False, False, 0, "ns0"),
    ("NS0 nunca se toca (completa)", 0, "AY4", False, False, 0, "ns0"),
    ("excepción «Muy fácil»: NS1 no sube", 1, "AY3", True, False, 1, "muy_facil"),
    ("riesgo R9: NS1 no sube", 1, "AY4", False, True, 1, "riesgo_r9"),
    ("riesgo R9: NS2 no baja", 2, "AY1", False, True, 2, "riesgo_r9"),
]


@pytest.mark.parametrize("nombre,ns,pref,mf,r9,final,motivo", CASOS_3_1, ids=[x[0] for x in CASOS_3_1])
def test_tabla_ajuste_3_1(nombre, ns, pref, mf, r9, final, motivo):
    assert aplicar_ajuste_3_1(ns, pref, todas_muy_facil=mf, riesgo_r9=r9) == (final, motivo)


def test_api_ajuste_3_1_se_aplica_y_guarda_el_ns_previo(client, db):
    r, _ = _enviar_completo(client, db, base="no_se", part3={"3.1": "a"})  # m = 0.25 → NS2; pista general → NS1
    assert r.status_code == 200, r.text
    assert set(_ns_por_codigo(db).values()) == {1}
    assert set(db.scalars(select(NivelSoporte.ns_maximo_historico))) == {2}  # PROVISIONAL: techo = NS previo al ajuste
    res = db.scalar(select(LineaBaseResultado))
    assert set(res.ns_inicial_por_concepto.values()) == {1}
    ajuste = res.banderas_iniciales["ajuste_ns_3_1"]
    assert all(ajuste[c] == {"previo": 2, "aplicado": 1, "motivo": "aplicado"} for c in CONCEPTOS)


def test_api_ajuste_3_1_no_se_aplica_con_riesgo_r9(client, db):
    r, _ = _enviar_completo(client, db, base="no_se", part1={"1.6": ["c"]}, part3={"3.1": "a", "3.2": "a"})
    assert r.status_code == 200, r.text
    assert set(_ns_por_codigo(db).values()) == {2}
    res = db.scalar(select(LineaBaseResultado))
    assert res.banderas_iniciales["r9"]["riesgo"] is True
    assert res.banderas_iniciales["ajuste_ns_3_1"]["join"]["motivo"] == "riesgo_r9"


# ---------- Dificultad inicial ----------
def _poner_diagnostico(db, dificultad=None, modo_3_4=None):
    prefs = {"3.4": modo_3_4} if modo_3_4 else {}
    db.add(
        LineaBaseResultado(
            usuario_id=ana(db).id, cuestionario_id=db.scalar(select(LineaBaseCuestionario.id)),
            dificultad_inicial=dificultad, preferencias=prefs,
        )
    )
    db.commit()


@pytest.mark.parametrize("inicial,esperado", [("D1", [True, False, False]), ("D2", [False, True, False]), ("D3", [False, False, True])])
def test_listado_marca_la_dificultad_inicial_sin_bloquear_las_demas(client, db, inicial, esperado):
    registrar(client)
    h = cabecera(token_de(client))
    ids = [crear_desafio(db, "filtrado", d, f"T{d}") for d in ("D1", "D2", "D3")]
    _poner_diagnostico(db, inicial)
    j = client.get(f"{API}/desafios", headers=h).json()
    assert [g["empieza_aqui"] for g in j["grupos"]] == esperado
    assert j["total"] == 3
    assert client.post(f"{API}/desafios/{ids[2]}/iniciar", headers=h).status_code == 200  # cualquiera se puede iniciar


def test_listado_sin_diagnostico_no_marca_ninguna(client, db):
    registrar(client)
    h = cabecera(token_de(client))
    crear_desafio(db)
    assert [g["empieza_aqui"] for g in client.get(f"{API}/desafios", headers=h).json()["grupos"]] == [False] * 3


# ---------- R13: preferencia 3.4 ----------
def _proponer_retiro(client, db, modo, ns=2):
    """Deja a Ana con 3 SA de 2 envíos (R1 corresponde); devuelve (cabecera, desafio, respuesta del 3.er cierre)."""
    registrar(client)
    h = cabecera(token_de(client))
    did = crear_desafio(db)
    if modo is not None:
        _poner_diagnostico(db, "D1", modo)
    poner_ns(db, ns)
    resolver_con_error(client, h, did)
    resolver_con_error(client, h, did)
    return h, did, resolver_con_error(client, h, did)


def _pendientes(client, h):
    return client.get(f"{API}/ajustes/pendientes", headers=h).json()["ajustes"]


@pytest.mark.parametrize("modo", [None, "automatico"])
def test_automatico_retira_en_el_acto(client, db, modo):
    h, did, j = _proponer_retiro(client, db, modo)
    assert (j["ajuste_nivel"]["ns_anterior"], j["ajuste_nivel"]["ns_nuevo"]) == (2, 1)
    assert estado(db).ns == 1 and _pendientes(client, h) == []
    assert db.scalar(select(AjustePendiente)) is None


def test_aviso_previo_no_retira_avisa_y_se_aplica_al_iniciar_el_siguiente_desafio(client, db):
    h, did, j = _proponer_retiro(client, db, "aviso_previo")
    assert j["ajuste_nivel"] is None and estado(db).ns == 2
    (m,) = j["mensajes"]
    assert m["tipo"] == "retiro_aviso" and m["clave"] == "retiro_aviso_previo" and m["ajuste_id"]
    assert m["texto"] == MENSAJES["retiro_aviso_previo"]["texto"].replace("{{concepto}}", NOMBRE)
    (p,) = _pendientes(client, h)
    assert p["id"] == m["ajuste_id"] and p["modo"] == "aviso_previo" and p["concepto"]["codigo"] == "filtrado"
    ev = db.scalars(select(EventoMotor).order_by(EventoMotor.id.desc())).first()
    assert (ev.regla, ev.resultado, ev.ns_antes, ev.ns_despues) == ("R1", "mantiene", 2, 2)
    assert ev.indicadores["r13"]["preferencia_3_4"] == "aviso_previo"
    assert db.scalar(select(HistorialNivel)) is None  # no hubo cambio de NS
    # siguiente desafío: se aplica
    ini = client.post(f"{API}/desafios/{did}/iniciar", headers=h).json()
    assert [x["tipo"] for x in ini["mensajes"]] == ["retiro"]
    fila = estado(db)
    assert fila.ns == 1 and fila.ns_previo_retiro == 2 and fila.desafios_desde_cambio == 0
    h1 = db.scalar(select(HistorialNivel))
    assert (h1.ns_anterior, h1.ns_nuevo, h1.regla) == (2, 1, "R1")
    assert db.scalar(select(AjustePendiente)).estado == "aplicado" and _pendientes(client, h) == []


def test_aviso_previo_mantener_la_ayuda_no_cambia_el_ns(client, db):
    h, did, j = _proponer_retiro(client, db, "aviso_previo")
    r = client.post(f"{API}/ajustes/{j['mensajes'][0]['ajuste_id']}/responder", json={"accion": "mantener"}, headers=h)
    assert r.status_code == 200 and r.json()["estado"] == "mantenido" and r.json()["ajuste_nivel"] is None
    ini = client.post(f"{API}/desafios/{did}/iniciar", headers=h).json()
    assert ini["mensajes"] == [] and estado(db).ns == 2 and _pendientes(client, h) == []
    assert db.scalar(select(HistorialNivel)) is None


def test_preguntar_espera_la_respuesta_y_no_se_aplica_solo(client, db):
    h, did, j = _proponer_retiro(client, db, "preguntar")
    (m,) = j["mensajes"]
    assert m["tipo"] == "retiro_pregunta" and m["texto"] == MENSAJES["retiro_preguntar"]["texto"].replace("{{concepto}}", NOMBRE)
    client.post(f"{API}/desafios/{did}/iniciar", headers=h)  # iniciar otro desafío NO lo aplica
    assert estado(db).ns == 2 and len(_pendientes(client, h)) == 1


def test_preguntar_aceptar_aplica_y_la_recaida_r3_sigue_funcionando(client, db):
    h, did, j = _proponer_retiro(client, db, "preguntar")
    r = client.post(f"{API}/ajustes/{j['mensajes'][0]['ajuste_id']}/responder", json={"accion": "aceptar"}, headers=h).json()
    assert r["estado"] == "aplicado" and (r["ajuste_nivel"]["ns_anterior"], r["ajuste_nivel"]["ns_nuevo"]) == (2, 1)
    fila = estado(db)
    assert fila.ns == 1 and fila.ns_previo_retiro == 2
    assert db.scalar(select(HistorialNivel.regla)) == "R1"
    assert abandonar(client, h, did)["ajuste_nivel"] is None  # 1.º desafío tras el retiro: NR
    rec = abandonar(client, h, did)  # 2.º: NR → recaída
    assert (rec["ajuste_nivel"]["ns_anterior"], rec["ajuste_nivel"]["ns_nuevo"]) == (1, 2)
    assert estado(db).ns == 2 and estado(db).pausa_retiros_restante == 3


def test_retiro_aviso_previo_aplicado_tambien_permite_la_recaida(client, db):
    h, did, _ = _proponer_retiro(client, db, "aviso_previo")
    assert abandonar(client, h, did)["ajuste_nivel"] is None  # iniciar aplica el retiro; este abandono es el 1.º tras él
    assert estado(db).ns == 1
    assert abandonar(client, h, did)["ajuste_nivel"]["ns_nuevo"] == 2


def test_preguntar_mantener_no_cambia_el_ns(client, db):
    h, did, j = _proponer_retiro(client, db, "preguntar")
    r = client.post(f"{API}/ajustes/{j['mensajes'][0]['ajuste_id']}/responder", json={"accion": "mantener"}, headers=h).json()
    assert r["estado"] == "mantenido" and estado(db).ns == 2 and _pendientes(client, h) == []
    assert db.scalar(select(HistorialNivel)) is None


def test_mantener_no_retira_ni_avisa_y_registra_que_se_cumplio_el_criterio(client, db):
    h, did, j = _proponer_retiro(client, db, "mantener")
    assert j["ajuste_nivel"] is None and j["mensajes"] == [] and estado(db).ns == 2
    assert db.scalar(select(AjustePendiente)) is None and _pendientes(client, h) == []
    ev = db.scalars(select(EventoMotor).order_by(EventoMotor.id.desc())).first()
    assert (ev.regla, ev.resultado) == ("R1", "mantiene") and ev.indicadores["r13"]["preferencia_3_4"] == "mantener"
    assert "criterio" in ev.detalle


def test_r2_tambien_respeta_la_preferencia(client, db):
    registrar(client)
    h = cabecera(token_de(client))
    did = crear_desafio(db)
    _poner_diagnostico(db, "D1", "preguntar")
    poner_ns(db, 3)
    resolver(client, h, did)
    resolver(client, h, did)
    j = resolver(client, h, did)  # 3 SA limpios: R2 propondría 3 → 1
    assert j["ajuste_nivel"] is None and estado(db).ns == 3
    a = db.scalar(select(AjustePendiente))
    assert (a.regla, a.ns_antes, a.ns_nuevo, a.estado) == ("R2", 3, 1, "pendiente")
    r = client.post(f"{API}/ajustes/{a.id}/responder", json={"accion": "aceptar"}, headers=h).json()
    assert r["ajuste_nivel"]["ns_nuevo"] == 1 and db.scalar(select(HistorialNivel.regla)) == "R2"


def test_no_se_duplica_el_pendiente_si_el_criterio_se_cumple_otra_vez(client, db):
    h, did, _ = _proponer_retiro(client, db, "preguntar")
    j = resolver_con_error(client, h, did)  # 4.º cierre, sin responder
    assert j["mensajes"] == []
    assert len(list(db.scalars(select(AjustePendiente)))) == 1


def test_un_pendiente_vencido_caduca(client, db):
    h, did, j = _proponer_retiro(client, db, "preguntar")
    fila = estado(db)
    fila.ns = 3  # otra regla movió el NS mientras tanto
    db.commit()
    r = client.post(f"{API}/ajustes/{j['mensajes'][0]['ajuste_id']}/responder", json={"accion": "aceptar"}, headers=h).json()
    assert r["estado"] == "caducado" and estado(db).ns == 3
    assert db.scalar(select(HistorialNivel)) is None


def test_responder_valida_dueno_estado_y_cuerpo(client, db):
    h, did, j = _proponer_retiro(client, db, "preguntar")
    aid = j["mensajes"][0]["ajuste_id"]
    registrar(client, "Luis", "luis@uni.edu")
    otro = cabecera(token_de(client, "luis@uni.edu"))
    assert client.post(f"{API}/ajustes/{aid}/responder", json={"accion": "aceptar"}, headers=otro).status_code == 404
    assert client.post(f"{API}/ajustes/{aid}/responder", json={"accion": "otra"}, headers=h).status_code == 422
    assert client.post(f"{API}/ajustes/99999/responder", json={"accion": "mantener"}, headers=h).status_code == 404
    assert client.post(f"{API}/ajustes/{aid}/responder", json={"accion": "mantener"}, headers=h).status_code == 200
    assert client.post(f"{API}/ajustes/{aid}/responder", json={"accion": "mantener"}, headers=h).status_code == 409
    assert _pendientes(client, otro) == []


def test_un_fallo_al_aplicar_el_aviso_previo_no_rompe_el_inicio(client, db, monkeypatch):
    h, did, _ = _proponer_retiro(client, db, "aviso_previo")
    from app.modules.ajustes import service

    monkeypatch.setattr(service.motor, "_guardar_cambio_ns", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("falla")))
    r = client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    assert r.status_code == 200 and estado(db).ns == 2
