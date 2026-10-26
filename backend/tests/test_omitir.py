"""Entrega 4: omitir un desafío (POST /desafios/{id}/omitir), R8 («Muy difícil») y R7 («Muy fácil»)."""
import pytest
from sqlalchemy import func, select

from app.modules.analitica.models import IndicadorHistorico
from app.modules.asistencia.config_llm import cargar_mensajes_fijos
from app.modules.auth.models import Usuario
from app.modules.desafios import hooks
from app.modules.desafios.models import Concepto, Desafio, SesionDesafio
from app.modules.linea_base.models import NivelSoporte, Omision
from app.modules.motor_retiro import motor
from app.modules.motor_retiro.models import EventoMotor, HistorialNivel, Verificacion
from conftest import API, cabecera, registrar, token_de
from test_desafios import SOLUCION, crear_desafio
from test_motor_integracion import _sesion as _sesion_cerrada
from test_linea_base import _consentir, _con, _cuestionario, _enviar, _payload_valido, _sesion

MENSAJES = cargar_mensajes_fijos()["mensajes"]
NOMBRE_FILTRADO = "Filtrado (WHERE)"
TEXTO_REFUERZO = MENSAJES["refuerzo"]["texto"].replace("{{concepto}}", NOMBRE_FILTRADO)


@pytest.fixture
def sin_sembrados(client, db):
    """Quita los desafíos que siembra el sistema para controlar exactamente cuáles hay."""
    db.execute(Desafio.__table__.delete())
    db.commit()


# ---------- ayudas de las pruebas ----------
def estudiante(client):
    registrar(client)
    return cabecera(token_de(client))


def ana(db):
    return db.scalar(select(Usuario).where(Usuario.correo == "ana@uni.edu"))


def concepto(db, codigo="filtrado"):
    return db.scalar(select(Concepto).where(Concepto.codigo == codigo))


def poner_ns(db, ns, codigo="filtrado"):
    db.add(NivelSoporte(usuario_id=ana(db).id, concepto_id=concepto(db, codigo).id, ns=ns, ns_maximo_historico=ns))
    db.commit()


def ns_de(db, codigo="filtrado"):
    db.expire_all()
    return db.scalar(select(NivelSoporte.ns).where(NivelSoporte.concepto_id == concepto(db, codigo).id))


def iniciar(client, h, did):
    return client.post(f"{API}/desafios/{did}/iniciar", headers=h)


def omitir(client, h, did, motivo):
    iniciar(client, h, did)
    return client.post(f"{API}/desafios/{did}/omitir", json={"motivo": motivo}, headers=h)


def abandonar(client, h, did):
    iniciar(client, h, did)
    return client.post(f"{API}/desafios/{did}/abandonar", headers=h).json()


def resolver(client, h, did):
    iniciar(client, h, did)
    return client.post(f"{API}/desafios/{did}/intentos", json={"codigo": SOLUCION}, headers=h).json()


def eventos(db):
    db.expire_all()
    return list(db.scalars(select(EventoMotor).order_by(EventoMotor.id)))


def contar(db, modelo) -> int:
    db.expire_all()
    return db.scalar(select(func.count()).select_from(modelo))


# ---------- el endpoint ----------
def test_omitir_cierra_la_sesion_como_omitida_y_guarda_la_omision(client, db, sin_sembrados):
    h = estudiante(client)
    did = crear_desafio(db, "filtrado", "D2", "Dificil")
    sid = iniciar(client, h, did).json()["sesion_id"]
    r = client.post(f"{API}/desafios/{did}/omitir", json={"motivo": "muy_dificil"}, headers=h)
    j = r.json()
    assert r.status_code == 200 and j["estado"] == "omitido" and j["motivo"] == "muy_dificil" and j["mensaje"]
    db.expire_all()
    ses = db.get(SesionDesafio, sid)
    assert ses.estado == "omitido" and ses.resultado_cierre is None and ses.fin is not None and ses.tiempo_activo_seg is not None
    om = db.scalar(select(Omision))
    assert (om.motivo, om.origen, om.desafio_id, om.sesion_id, om.concepto_id, om.usuario_id) == (
        "muy_dificil", "desafio", did, sid, concepto(db).id, ana(db).id,
    )
    # No es resuelto, ni abandonado, ni queda en curso; se puede volver a empezar con una sesión nueva.
    assert client.get(f"{API}/desafios/{did}", headers=h).json()["estado"] == "sin_iniciar"
    p = client.get(f"{API}/progreso/resumen", headers=h).json()
    assert p["desafios_resueltos"] == 0 and p["sesiones_abandonadas"] == 0
    otra = iniciar(client, h, did).json()
    assert otra["sesion_id"] != sid and otra["reanudada"] is False


def test_omitir_valida_motivo_sesion_y_desafio(client, db, sin_sembrados):
    h = estudiante(client)
    did = crear_desafio(db)
    assert client.post(f"{API}/desafios/{did}/omitir", json={"motivo": "muy_facil"}, headers=h).status_code == 409  # nada en curso
    iniciar(client, h, did)
    r = client.post(f"{API}/desafios/{did}/omitir", json={"motivo": "aburrido"}, headers=h)
    assert r.status_code == 422 and "muy fácil o muy difícil" in r.json()["mensaje"]
    assert client.post(f"{API}/desafios/{did}/omitir", json={}, headers=h).status_code == 422
    assert contar(db, Omision) == 0  # los rechazos no dejan nada guardado
    assert client.post(f"{API}/desafios/9999/omitir", json={"motivo": "muy_facil"}, headers=h).status_code == 404
    assert client.post(f"{API}/desafios/{did}/omitir", json={"motivo": "muy_facil"}).status_code == 401
    assert client.post(f"{API}/desafios/{did}/omitir", json={"motivo": "muy_facil"}, headers=h).status_code == 200
    assert client.post(f"{API}/desafios/{did}/omitir", json={"motivo": "muy_facil"}, headers=h).status_code == 409  # ya cerrada


# ---------- R8 ----------
def test_r8_sube_el_ns_y_sugiere_un_desafio_mas_basico(client, db, sin_sembrados):
    h = estudiante(client)
    basico = crear_desafio(db, "filtrado", "D1", "Basico")
    dificil = crear_desafio(db, "filtrado", "D2", "Dificil")
    poner_ns(db, 1)
    j = omitir(client, h, dificil, "muy_dificil").json()
    assert j["ajuste_nivel"] == {"concepto": NOMBRE_FILTRADO, "ns_anterior": 1, "ns_nuevo": 2, "motivo": TEXTO_REFUERZO}
    assert j["sugerido"] == {"id": basico, "titulo": "Basico", "dificultad": "D1"}
    assert j["verificacion"] is None
    assert {m["tipo"] for m in j["mensajes"]} == {"refuerzo", "sugerencia"}
    sugerencia = next(m for m in j["mensajes"] if m["tipo"] == "sugerencia")
    assert sugerencia["texto"] == MENSAJES["sugerencia_mas_basico"]["texto"].replace("{{concepto}}", NOMBRE_FILTRADO).replace("{{desafio}}", "Basico")
    assert ns_de(db) == 2
    hist = db.scalar(select(HistorialNivel))
    assert (hist.ns_anterior, hist.ns_nuevo, hist.regla) == (1, 2, "R8")
    ev = eventos(db)[-1]
    assert (ev.regla, ev.resultado, ev.ns_antes, ev.ns_despues) == ("R8", "cambio", 1, 2)
    assert ev.indicadores["omision"] == "muy_dificil" and ev.indicadores["sugerido_id"] == basico


def test_r8_sin_desafio_mas_basico_devuelve_sugerido_nulo(client, db, sin_sembrados):
    h = estudiante(client)
    solo = crear_desafio(db, "filtrado", "D1", "Unico")
    j = omitir(client, h, solo, "muy_dificil").json()
    assert j["sugerido"] is None and j["ajuste_nivel"]["ns_nuevo"] == 2
    assert {m["tipo"] for m in j["mensajes"]} == {"refuerzo"}
    # tampoco hay uno más básico si los demás son de la misma dificultad o mayor
    crear_desafio(db, "filtrado", "D3", "Mas dificil")
    assert omitir(client, h, solo, "muy_dificil").json()["sugerido"] is None


def test_r8_prefiere_un_desafio_no_resuelto_y_el_mas_cercano(client, db, sin_sembrados):
    h = estudiante(client)
    d1 = crear_desafio(db, "filtrado", "D1", "Uno")
    d2 = crear_desafio(db, "filtrado", "D2", "Dos")
    d3 = crear_desafio(db, "filtrado", "D3", "Tres")
    assert omitir(client, h, d3, "muy_dificil").json()["sugerido"]["id"] == d2  # el más cercano por debajo
    resolver(client, h, d2)
    assert omitir(client, h, d3, "muy_dificil").json()["sugerido"]["id"] == d1  # D2 ya resuelto: se prefiere uno sin resolver


@pytest.mark.parametrize("ns,esperado", [(0, 1), (1, 2), (2, 3), (3, 3)])
def test_r8_tabla_de_ns_con_maximo_3(client, db, sin_sembrados, ns, esperado):
    h = estudiante(client)
    did = crear_desafio(db, "filtrado", "D2", "Dificil")
    poner_ns(db, ns)
    j = omitir(client, h, did, "muy_dificil").json()
    assert ns_de(db) == esperado
    assert (j["ajuste_nivel"] is None) == (ns == 3)
    assert contar(db, HistorialNivel) == (0 if ns == 3 else 1)


def test_r8_reinicia_la_ventana_y_cambia_la_primera_ayuda(client, db, sin_sembrados):
    h = estudiante(client)
    did = crear_desafio(db, "filtrado", "D2", "Dificil")
    omitir(client, h, did, "muy_dificil")  # NS 1 → 2
    fila = db.scalar(select(NivelSoporte))
    assert fila.ns == 2 and fila.desafios_desde_cambio == 0 and fila.ns_maximo_historico == 2 and fila.ultimo_cambio_en
    iniciar(client, h, did)
    assert client.post(f"{API}/desafios/{did}/ayuda", json={}, headers=h).json()["tipo_ayuda"] == "AY2"  # NS2: primera ayuda AY2


def test_r8_dos_omisiones_seguidas_con_ns3_se_registran_para_r6(client, db, sin_sembrados):
    h = estudiante(client)
    facil = crear_desafio(db, "filtrado", "D1", "Facil")
    dificil = crear_desafio(db, "filtrado", "D2", "Dificil")
    poner_ns(db, 3)
    primera = omitir(client, h, dificil, "muy_dificil").json()
    segunda = omitir(client, h, dificil, "muy_dificil").json()
    assert primera["ajuste_nivel"] is None and segunda["ajuste_nivel"] is None and ns_de(db) == 3
    assert segunda["sugerido"]["id"] == facil
    ev = eventos(db)
    assert "r6_b_pendiente" not in ev[0].indicadores and ev[1].indicadores["r6_b_pendiente"] is True
    assert "R6 (b)" in ev[1].detalle and ev[1].indicadores["omisiones_muy_dificil_seguidas"] == 2


def test_r8_las_omisiones_seguidas_se_cortan_con_otro_cierre(client, db, sin_sembrados):
    h = estudiante(client)
    facil = crear_desafio(db, "filtrado", "D1", "Facil")
    dificil = crear_desafio(db, "filtrado", "D2", "Dificil")
    poner_ns(db, 3)
    omitir(client, h, dificil, "muy_dificil")
    resolver(client, h, facil)  # un cierre entre las dos omisiones
    omitir(client, h, dificil, "muy_dificil")
    assert "r6_b_pendiente" not in eventos(db)[-1].indicadores
    assert eventos(db)[-1].indicadores["omisiones_muy_dificil_seguidas"] == 1


def test_r8_en_ns2_dos_seguidas_no_registran_r6_porque_el_ns_no_era_3(client, db, sin_sembrados):
    h = estudiante(client)
    dificil = crear_desafio(db, "filtrado", "D2", "Dificil")
    poner_ns(db, 1)
    omitir(client, h, dificil, "muy_dificil")  # 1 → 2
    omitir(client, h, dificil, "muy_dificil")  # 2 → 3, el NS no era 3 al llegar
    assert ns_de(db) == 3 and "r6_b_pendiente" not in eventos(db)[-1].indicadores
    omitir(client, h, dificil, "muy_dificil")  # tercera seguida, ahora sí estaba en 3
    assert eventos(db)[-1].indicadores["r6_b_pendiente"] is True


# ---------- las omisiones no entran en la ventana ----------
def test_las_omisiones_no_entran_en_la_ventana(client, db, sin_sembrados):
    h = estudiante(client)
    did = crear_desafio(db)
    abandonar(client, h, did)
    abandonar(client, h, did)
    om = omitir(client, h, did, "muy_facil").json()
    assert om["ajuste_nivel"] is None and ns_de(db) is None  # sin registro: NS por defecto, nada cambió
    ev_om = eventos(db)[-1]
    assert (ev_om.regla, ev_om.resultado) == ("R4", "mantiene") and ev_om.indicadores["omision"] == "muy_facil"
    assert ev_om.indicadores["n"] == 2 and ev_om.indicadores["desafios_desde_cambio"] == 2  # la omisión no cuenta
    j = abandonar(client, h, did)  # tercer cierre real: R5
    assert j["ajuste_nivel"]["ns_nuevo"] == 2
    ev = eventos(db)[-1]
    assert ev.regla == "R5" and ev.indicadores["n"] == 3 and ev.indicadores["desafios_desde_cambio"] == 3


def test_una_omision_no_deja_fila_en_el_historico_de_indicadores(client, db, sin_sembrados):
    h = estudiante(client)
    did = crear_desafio(db)
    omitir(client, h, did, "muy_facil")
    assert contar(db, IndicadorHistorico) == 0
    abandonar(client, h, did)
    assert contar(db, IndicadorHistorico) == 1


def test_una_omision_no_evalua_r5_ni_r1_aunque_la_ventana_ya_los_cumpla(client, db, sin_sembrados):
    h = estudiante(client)
    did = crear_desafio(db)
    uid = ana(db).id
    for minutos in (30, 20, 10):  # tres NR ya cerrados sin pasar por el motor: R5 corresponde si se evalúa la ventana
        _sesion_cerrada(db, uid, did, minutos, "NR", intentos=3)
    j = omitir(client, h, did, "muy_facil").json()
    assert j["ajuste_nivel"] is None and ns_de(db) is None
    ev = eventos(db)[-1]
    assert ev.regla == "R4" and ev.indicadores["n"] == 3 and ev.indicadores["ta"] == 0.0  # la ventana se calcula, pero no se aplica
    assert abandonar(client, h, did)["ajuste_nivel"]["ns_nuevo"] == 2  # un cierre real sí la evalúa (R5)


# ---------- R7 ----------
def test_r7_dos_omisiones_muy_facil_asignan_verificacion_sin_cambiar_el_ns(client, db, sin_sembrados):
    h = estudiante(client)
    a = crear_desafio(db, "filtrado", "D1", "A")
    b = crear_desafio(db, "filtrado", "D2", "B")
    primera = omitir(client, h, a, "muy_facil").json()
    assert primera["verificacion"] is None and primera["ajuste_nivel"] is None and primera["sugerido"] is None
    segunda = omitir(client, h, a, "muy_facil").json()
    assert segunda["verificacion"] == {
        "concepto": NOMBRE_FILTRADO, "desafio_id": b, "titulo": "B", "dificultad": "D2",
        "mensaje": MENSAJES["verificacion"]["texto"],
    }
    assert segunda["ajuste_nivel"] is None and ns_de(db) is None and contar(db, HistorialNivel) == 0  # no retira por sí sola
    assert [m["tipo"] for m in segunda["mensajes"]] == ["verificacion"]
    v = db.scalar(select(Verificacion))
    assert (v.desafio_id, v.origen, v.estado, v.usuario_id) == (b, "desafio", "pendiente", ana(db).id)
    ev = eventos(db)[-1]
    assert ev.regla == "R7" and ev.indicadores["omisiones_muy_facil"] == 2 and ev.indicadores["verificacion_id"] == b


def test_r7_el_contador_se_reinicia_y_una_verificacion_pendiente_bloquea_otra(client, db, sin_sembrados):
    h = estudiante(client)
    a = crear_desafio(db, "filtrado", "D1", "A")
    crear_desafio(db, "filtrado", "D2", "B")
    omitir(client, h, a, "muy_facil")
    assert omitir(client, h, a, "muy_facil").json()["verificacion"] is not None
    assert omitir(client, h, a, "muy_facil").json()["verificacion"] is None  # contador en 1 tras el reinicio
    assert eventos(db)[-1].indicadores["omisiones_muy_facil"] == 1
    assert omitir(client, h, a, "muy_facil").json()["verificacion"] is None  # llega a 2 pero ya hay una pendiente
    assert contar(db, Verificacion) == 1


def test_r7_muy_dificil_no_suma_al_contador_de_muy_facil(client, db, sin_sembrados):
    h = estudiante(client)
    a = crear_desafio(db, "filtrado", "D1", "A")
    crear_desafio(db, "filtrado", "D2", "B")
    omitir(client, h, a, "muy_facil")
    omitir(client, h, a, "muy_dificil")
    assert omitir(client, h, a, "muy_facil").json()["verificacion"] is not None  # son 2 «Muy fácil» en total


def test_r7_el_contador_es_por_concepto(client, db, sin_sembrados):
    h = estudiante(client)
    f = crear_desafio(db, "filtrado", "D1", "F")
    crear_desafio(db, "filtrado", "D2", "F2")
    o = crear_desafio(db, "ordenamiento", "D1", "O")
    omitir(client, h, f, "muy_facil")
    assert omitir(client, h, o, "muy_facil").json()["verificacion"] is None  # 1 de filtrado + 1 de ordenamiento: no suman


def test_r7_suma_las_omisiones_de_la_linea_base_y_las_de_los_desafios(client, db, sin_sembrados):
    h = estudiante(client)
    a = crear_desafio(db, "filtrado", "D1", "A")
    b = crear_desafio(db, "filtrado", "D2", "B")
    db.add(Omision(usuario_id=ana(db).id, concepto_id=concepto(db).id, desafio_id=None, motivo="muy_facil", origen="linea_base"))
    db.commit()
    j = omitir(client, h, a, "muy_facil").json()  # 1 de la línea base + 1 de este desafío
    assert j["verificacion"]["desafio_id"] == b


def test_r7_concepto_con_un_solo_desafio_verifica_con_ese_mismo(client, db, sin_sembrados):
    h = estudiante(client)
    unico = crear_desafio(db, "conteo_agregacion", "D1", "Unico")
    omitir(client, h, unico, "muy_facil")
    assert omitir(client, h, unico, "muy_facil").json()["verificacion"]["desafio_id"] == unico


def test_r7_sin_ningun_desafio_disponible_no_asigna_y_conserva_el_contador(client, db, sin_sembrados):
    h = estudiante(client)
    a = crear_desafio(db, "filtrado", "D1", "A")
    b = crear_desafio(db, "filtrado", "D2", "B")
    resolver(client, h, a)
    resolver(client, h, b)  # los dos desafíos del concepto ya están resueltos: no queda candidato para verificar
    omitir(client, h, a, "muy_facil")
    j = omitir(client, h, a, "muy_facil").json()
    assert j["verificacion"] is None and contar(db, Verificacion) == 0
    assert "sin desafío disponible" in eventos(db)[-1].detalle
    assert omitir(client, h, a, "muy_facil").json()["verificacion"] is None  # sigue sin haberlo (el contador no se reinició)


def test_la_verificacion_se_marca_en_el_listado_y_en_el_detalle(client, db, sin_sembrados):
    h = estudiante(client)
    a = crear_desafio(db, "filtrado", "D1", "A")
    b = crear_desafio(db, "filtrado", "D2", "B")
    assert client.get(f"{API}/desafios/{b}", headers=h).json()["verificacion"] is False
    omitir(client, h, a, "muy_facil")
    omitir(client, h, a, "muy_facil")
    assert client.get(f"{API}/desafios/{b}", headers=h).json()["verificacion"] is True
    assert client.get(f"{API}/desafios/{a}", headers=h).json()["verificacion"] is False
    marcas = {d["id"]: d["verificacion"] for g in client.get(f"{API}/desafios", headers=h).json()["grupos"] for d in g["desafios"]}
    assert marcas == {a: False, b: True}


def test_resolver_la_verificacion_sin_ayuda_la_completa_como_sa(client, db, sin_sembrados):
    h = estudiante(client)
    a = crear_desafio(db, "filtrado", "D1", "A")
    b = crear_desafio(db, "filtrado", "D2", "B")
    omitir(client, h, a, "muy_facil")
    omitir(client, h, a, "muy_facil")
    j = resolver(client, h, b)
    assert j["resultado_cierre"] == "SA"
    db.expire_all()
    v = db.scalar(select(Verificacion))
    assert (v.estado, v.resultado) == ("completada", "SA") and v.sesion_id is not None and v.completada_en is not None
    assert client.get(f"{API}/desafios/{b}", headers=h).json()["verificacion"] is False
    # es un cierre normal más de la ventana (así contará como el primero de los 3 limpios de R2 en la entrega 5)
    assert eventos(db)[-1].indicadores["n"] == 1 and eventos(db)[-1].indicadores["resultado_sesion"] == "SA"


def test_en_la_verificacion_la_ayuda_sigue_disponible_pero_ya_no_cuenta_como_sa(client, db, sin_sembrados):
    h = estudiante(client)
    a = crear_desafio(db, "filtrado", "D1", "A")
    b = crear_desafio(db, "filtrado", "D2", "B")
    omitir(client, h, a, "muy_facil")
    omitir(client, h, a, "muy_facil")
    iniciar(client, h, b)
    r = client.post(f"{API}/desafios/{b}/ayuda", json={}, headers=h)
    assert r.status_code == 200 and r.json()["tipo_ayuda"] == "AY1"
    j = client.post(f"{API}/desafios/{b}/intentos", json={"codigo": SOLUCION}, headers=h).json()
    assert j["resultado_cierre"] == "CP"
    db.expire_all()
    assert db.scalar(select(Verificacion.resultado)) == "CP"


def test_abandonar_la_verificacion_la_completa_como_nr(client, db, sin_sembrados):
    h = estudiante(client)
    a = crear_desafio(db, "filtrado", "D1", "A")
    b = crear_desafio(db, "filtrado", "D2", "B")
    omitir(client, h, a, "muy_facil")
    omitir(client, h, a, "muy_facil")
    abandonar(client, h, b)
    db.expire_all()
    assert (db.scalar(select(Verificacion.estado)), db.scalar(select(Verificacion.resultado))) == ("completada", "NR")


def test_omitir_la_propia_verificacion_la_completa_como_omitida(client, db, sin_sembrados):
    h = estudiante(client)
    a = crear_desafio(db, "filtrado", "D1", "A")
    b = crear_desafio(db, "filtrado", "D2", "B")
    omitir(client, h, a, "muy_facil")
    omitir(client, h, a, "muy_facil")
    omitir(client, h, b, "muy_dificil")
    db.expire_all()
    assert (db.scalar(select(Verificacion.estado)), db.scalar(select(Verificacion.resultado))) == ("completada", "omitido")


def test_omitir_el_mismo_desafio_unico_no_completa_su_propia_verificacion(client, db, sin_sembrados):
    h = estudiante(client)
    unico = crear_desafio(db, "conteo_agregacion", "D1", "Unico")
    omitir(client, h, unico, "muy_facil")
    omitir(client, h, unico, "muy_facil")  # la verificación se asigna con el mismo desafío, tras esta sesión
    db.expire_all()
    assert db.scalar(select(Verificacion.estado)) == "pendiente"


# ---------- diagnóstico: verificación al terminar ----------
def test_diagnostico_con_dos_items_omitidos_muy_facil_asigna_verificacion(client, db):
    h = _sesion(client)
    _consentir(client, h)
    payload = _payload_valido(_cuestionario(client, h))
    for pregunta in ("P1", "P4"):  # los dos ítems de filtrado
        payload = _con(payload, pregunta, opciones=[], confianza=None, omitir="muy_facil")
    r = _enviar(client, h, payload)
    assert r.status_code == 200
    ver = r.json()["verificaciones"]
    assert len(ver) == 1 and ver[0]["concepto"] == NOMBRE_FILTRADO and ver[0]["mensaje"] == MENSAJES["verificacion"]["texto"]
    ids_filtrado = set(db.scalars(select(Desafio.id).where(Desafio.concepto_id == concepto(db).id)))
    assert ver[0]["desafio_id"] in ids_filtrado
    assert ns_de(db) == 1  # excepción de R0: todos «Muy fácil» → NS1, no 0
    v = db.scalar(select(Verificacion))
    assert (v.origen, v.estado, v.desafio_id) == ("linea_base", "pendiente", ver[0]["desafio_id"])
    assert client.get(f"{API}/desafios/{v.desafio_id}", headers=h).json()["verificacion"] is True


def test_diagnostico_con_un_solo_item_omitido_espera_a_la_siguiente_omision_en_un_desafio(client, db):
    h = _sesion(client)
    _consentir(client, h)
    payload = _con(_payload_valido(_cuestionario(client, h)), "P5", opciones=[], confianza=None, omitir="muy_facil")  # join: 1 ítem
    r = _enviar(client, h, payload)
    assert r.status_code == 200 and r.json()["verificaciones"] == [] and contar(db, Verificacion) == 0
    join = list(db.scalars(select(Desafio.id).where(Desafio.concepto_id == concepto(db, "join").id).order_by(Desafio.id)))
    assert len(join) >= 2
    j = omitir(client, h, join[0], "muy_facil").json()  # 1 de la línea base + 1 de este desafío
    assert j["verificacion"] is not None and j["verificacion"]["desafio_id"] != join[0]


def test_diagnostico_sin_omisiones_no_asigna_verificaciones(client, db):
    h = _sesion(client)
    _consentir(client, h)
    r = _enviar(client, h, _payload_valido(_cuestionario(client, h)))
    assert r.status_code == 200 and r.json()["verificaciones"] == [] and contar(db, Verificacion) == 0


def test_un_fallo_al_asignar_la_verificacion_inicial_no_deshace_el_diagnostico(client, db, monkeypatch):
    from app.modules.linea_base import service as lb_service

    def falla(*_a, **_k):
        raise RuntimeError("sin desafíos")

    monkeypatch.setattr(lb_service.verificaciones, "asignar_tras_linea_base", falla)
    h = _sesion(client)
    _consentir(client, h)
    payload = _payload_valido(_cuestionario(client, h))
    for pregunta in ("P1", "P4"):
        payload = _con(payload, pregunta, opciones=[], confianza=None, omitir="muy_facil")
    r = _enviar(client, h, payload)
    assert r.status_code == 200 and r.json()["verificaciones"] == [] and r.json()["linea_base_completada"] is True
    db.expire_all()
    assert ana(db).linea_base_completada is True


# ---------- el motor nunca rompe la omisión ----------
def test_un_fallo_del_hook_no_rompe_la_omision(client, db, sin_sembrados, monkeypatch):
    h = estudiante(client)
    did = crear_desafio(db)

    def falla(_db, _ses):
        raise RuntimeError("motor caído")

    monkeypatch.setattr(hooks, "al_omitir_desafio", falla)
    r = omitir(client, h, did, "muy_dificil")
    j = r.json()
    assert r.status_code == 200 and j["estado"] == "omitido"
    assert j["ajuste_nivel"] is None and j["sugerido"] is None and j["verificacion"] is None and j["mensajes"] == []
    assert contar(db, Omision) == 1


def test_un_fallo_dentro_del_motor_se_registra_y_no_rompe_la_omision(client, db, sin_sembrados, monkeypatch):
    h = estudiante(client)
    did = crear_desafio(db)
    poner_ns(db, 1)

    def sin_reglas():
        raise OSError("reglas.json ilegible")

    monkeypatch.setattr(motor, "cargar_reglas", sin_reglas)
    r = omitir(client, h, did, "muy_dificil")
    j = r.json()
    assert r.status_code == 200 and j["estado"] == "omitido" and j["ajuste_nivel"] is None
    assert ns_de(db) == 1  # el NS se mantiene
    ev = eventos(db)[-1]
    assert ev.resultado == "error" and "reglas.json ilegible" in ev.detalle
    assert contar(db, Omision) == 1


# ---------- los mensajes del motor salen de un único punto ----------
def test_los_mensajes_del_motor_se_construyen_en_mensajes_py():
    from app.modules.motor_retiro import mensajes

    assert mensajes.texto_fijo("refuerzo", concepto="JOIN") == MENSAJES["refuerzo"]["texto"].replace("{{concepto}}", "JOIN")
    assert mensajes.texto_fijo("clave_inexistente") is None and mensajes.texto_fijo(None) is None
    assert mensajes.texto_cambio_ns("clave_inexistente", "JOIN", 1, 2) == "Tu nivel de ayuda en JOIN pasó de 1 a 2."
    m = mensajes.mensaje("verificacion", concepto="JOIN")
    assert (m.clave, m.tipo, m.texto) == ("verificacion", "verificacion", MENSAJES["verificacion"]["texto"])
    assert mensajes.mensaje("sugerencia_mas_basico", concepto="JOIN", desafio="X").tipo == "sugerencia"
    assert "{{" not in mensajes.mensaje("sugerencia_mas_basico", concepto="JOIN", desafio="X").texto
