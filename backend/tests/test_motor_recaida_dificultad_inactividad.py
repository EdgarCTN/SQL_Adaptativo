"""Entrega 6: R3 recaída, R12 cambio de dificultad y R14 inactividad (más la pausa de 3 desafíos sobre R1 y R2)."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.core.db import ahora_utc
from app.core.reglas import cargar_reglas
from app.modules.asistencia.config_llm import cargar_mensajes_fijos
from app.modules.desafios.models import Concepto, Desafio, SesionDesafio
from app.modules.linea_base.models import NivelSoporte
from app.modules.motor_retiro import mensajes as mensajes_motor
from app.modules.motor_retiro.cambio_dificultad import evaluar_cambio_dificultad
from app.modules.motor_retiro.evaluador import evaluar
from app.modules.motor_retiro.inactividad import esta_inactivo, ns_tras_inactividad
from app.modules.motor_retiro.models import EventoMotor, HistorialNivel
from conftest import API, cabecera, login as hacer_login, registrar, token_de
from test_desafios import SOLUCION, crear_desafio
from test_motor_integracion import abandonar, ana, concepto, estado, poner_historial, poner_ns, preparar, resolver, resolver_con_error
from test_motor_reglas import SA3, SA3_2INT, c, ctx

MENSAJES = cargar_mensajes_fijos()["mensajes"]
CFG = cargar_reglas()
NOMBRE = "Filtrado (WHERE)"


@pytest.fixture(autouse=True)
def _sin_sembrados(client, db):
    db.execute(Desafio.__table__.delete())
    db.commit()


# ---------- Tablas de casos (reglas puras) ----------
# (nombre, ns_actual, ns_previo_retiro, cierres, desafios_desde_cambio, regla esperada, ns esperado)
CASOS_R3 = [
    ("R3: retiro R1 de 2 a 1, luego NR y CE → vuelve a 2", 1, 2, [c("NR", 0), c("CE", 2)], None, "R3", 2),
    ("R3: retiro R2 de 3 a 1, luego CE y CE → vuelve a 3", 1, 3, [c("CE", 2), c("CE", 3)], None, "R3", 3),
    ("R3: retiro a NS0, luego NR y NR → vuelve a 1", 0, 1, [c("NR", 0), c("NR", 0)], None, "R3", 1),
    ("R3 no aplica si uno de los 2 es SA", 1, 2, [c("SA"), c("CE", 2)], None, "R4", 1),
    ("R3 no aplica si el primero es CE y el segundo CP", 1, 2, [c("CE", 2), c("CP")], None, "R4", 1),
    ("R3 no aplica con un solo desafío tras el retiro", 1, 2, [c("NR", 0)], None, "R4", 1),
    ("R3 solo mira los 2 primeros: al 3.º ya no corresponde (corresponde R5)", 1, 2, [c("NR", 0), c("NR", 0), c("NR", 0)], None, "R5", 2),
    ("R3 no aplica si el último cambio no fue un retiro (sin NS previo)", 1, None, [c("NR", 0), c("NR", 0)], None, "R4", 1),
    ("R3 no aplica si el NS previo no es mayor que el actual", 2, 2, [c("NR", 0), c("NR", 0)], None, "R4", 2),
]


@pytest.mark.parametrize("nombre,ns,previo,cierres,desde,regla,esperado", CASOS_R3, ids=[x[0] for x in CASOS_R3])
def test_tabla_r3(nombre, ns, previo, cierres, desde, regla, esperado):
    ev = evaluar(ctx(ns, cierres, desde, ns_previo_retiro=previo))
    assert (ev.regla, ev.ns_nuevo) == (regla, esperado), ev.motivo
    if regla == "R3":
        assert ev.clave_mensaje == "recaida" and ev.pausa_retiros == 3 and ev.accion == "cambiar_ns"


def test_r3_no_se_evalua_al_omitir():
    ev = evaluar(ctx(1, [c("NR", 0), c("NR", 0)], ns_previo_retiro=2, omision_motivo="muy_dificil"))
    assert ev.regla != "R3"


def test_r3_usa_los_umbrales_de_reglas_json():
    import copy

    cfg = copy.deepcopy(CFG)
    cfg["recaida_y_pausas"]["desafios_ce_nr_para_recaida"] = 3
    cfg["recaida_y_pausas"]["desafios_sin_retiro_tras_recaida_o_cambio_dificultad"] = 5
    assert evaluar(ctx(1, [c("NR", 0)] * 2, ns_previo_retiro=2, config=cfg)).regla == "R4"
    ev = evaluar(ctx(1, [c("CE", 2), c("NR", 0), c("CE", 2)], ns_previo_retiro=2, config=cfg))
    assert (ev.regla, ev.pausa_retiros) == ("R3", 5)


# (nombre, ns, cierres, pausa, regla esperada, ns esperado)
CASOS_PAUSA = [
    ("sin pausa R1 retira", 2, SA3_2INT, 0, "R1", 1),
    ("con pausa R1 no retira", 2, SA3_2INT, 1, "R4", 2),
    ("sin pausa R2 retira 2", 3, SA3, 0, "R2", 1),
    ("con pausa R2 no retira (ni R1 la sustituye)", 3, SA3, 3, "R4", 3),
    ("la pausa no bloquea el refuerzo R5", 1, [c("NR", 0)] * 3, 3, "R5", 2),
]


@pytest.mark.parametrize("nombre,ns,cierres,pausa,regla,esperado", CASOS_PAUSA, ids=[x[0] for x in CASOS_PAUSA])
def test_tabla_pausa_de_retiros(nombre, ns, cierres, pausa, regla, esperado):
    ev = evaluar(ctx(ns, cierres, pausa_retiros=pausa))
    assert (ev.regla, ev.ns_nuevo) == (regla, esperado), ev.motivo


# (nombre, ns, dificultad nueva, mayor cerrada, mayor en curso, ¿cambia la dificultad?, ns esperado, ¿cambia el NS?)
CASOS_R12 = [
    ("D1 cerrada, inicia D2 con NS0 → NS1", 0, "D2", "D1", None, True, 1, True),
    ("D1 cerrada, inicia D3 con NS0 → NS1", 0, "D3", "D1", None, True, 1, True),
    ("D1 cerrada, inicia D2 con NS2 → se queda en 2", 2, "D2", "D1", None, True, 2, False),
    ("D2 cerrada, inicia D3 con NS3 → se queda en 3", 3, "D3", "D2", None, True, 3, False),
    ("D1 cerrada, inicia D1 → no hay cambio", 0, "D1", "D1", None, False, 0, False),
    ("D2 cerrada, inicia D1 → no hay cambio", 0, "D1", "D2", None, False, 0, False),
    ("D2 cerrada, inicia D2 → no hay cambio", 1, "D2", "D2", None, False, 1, False),
    ("nada cerrado en el concepto → es el primero, no hay cambio", 0, "D2", None, None, False, 0, False),
    ("ya tiene un D2 en curso → el segundo D2 no repite la regla", 0, "D2", "D1", "D2", False, 0, False),
    ("tiene un D2 en curso e inicia D3 → sí cambia", 0, "D3", "D1", "D2", True, 1, True),
]


@pytest.mark.parametrize("nombre,ns,nueva,cerrada,en_curso,cambia,ns_esp,cambia_ns", CASOS_R12, ids=[x[0] for x in CASOS_R12])
def test_tabla_r12(nombre, ns, nueva, cerrada, en_curso, cambia, ns_esp, cambia_ns):
    d = evaluar_cambio_dificultad(ns, nueva, cerrada, en_curso, CFG)
    if not cambia:
        assert d is None
        return
    assert (d.ns_nuevo, d.cambia_ns, d.pausa_retiros) == (ns_esp, cambia_ns, 3), d.motivo


# (nombre, ns, máximo histórico, ns esperado)
CASOS_R14 = [
    ("sube 1 si no supera el máximo", 1, 3, 2),
    ("no supera el máximo histórico", 2, 2, 2),
    ("desde NS0 con máximo 3 sube solo 1", 0, 3, 1),
    ("NS0 con máximo 0 (nunca estuvo más alto) no sube", 0, 0, 0),
    ("NS3 no pasa de 3", 3, 3, 3),
    ("nunca baja aunque el máximo sea menor", 2, 1, 2),
]


@pytest.mark.parametrize("nombre,ns,maximo,esperado", CASOS_R14, ids=[x[0] for x in CASOS_R14])
def test_tabla_r14(nombre, ns, maximo, esperado):
    assert ns_tras_inactividad(ns, maximo) == esperado


def test_r14_umbral_de_dias():
    ahora = datetime(2026, 10, 29, 12, tzinfo=timezone.utc)
    assert not esta_inactivo(ahora - timedelta(days=13, hours=23), ahora, 14)
    assert esta_inactivo(ahora - timedelta(days=14), ahora, 14)
    assert esta_inactivo(ahora - timedelta(days=40), ahora, 14)
    assert not esta_inactivo(None, ahora, 14)  # sin ninguna sesión no hay actividad que retomar
    assert esta_inactivo(datetime(2026, 10, 1), ahora, 14)  # fechas sin zona se tratan como UTC


def test_unir_nombres_para_el_reenganche():
    assert mensajes_motor.unir_nombres(["A"]) == "A"
    assert mensajes_motor.unir_nombres(["A", "B"]) == "A y B"
    assert mensajes_motor.unir_nombres(["A", "B", "C"]) == "A, B y C"
    assert mensajes_motor.unir_nombres(["A", "B", "C", "D", "E"]) == "A, B, C y 2 más"


def test_r3_r12_y_r14_no_cuentan_como_refuerzo_previo_de_r6():
    assert not {"R3", "R12", "R14"} & set(CFG["r6_estancamiento"]["reglas_que_cuentan_como_refuerzo"])


# ---------- R3 integración ----------
def _retirar_r1(client, db, h, did, ns=2):
    poner_ns(db, ns)
    for _ in range(2):
        assert resolver_con_error(client, h, did)["ajuste_nivel"] is None
    j = resolver_con_error(client, h, did)
    assert j["ajuste_nivel"]["ns_anterior"] == ns and j["ajuste_nivel"]["ns_nuevo"] == ns - 1


def test_recaida_tras_retiro_r1_vuelve_al_ns_previo_con_mensaje_y_pausa(client, db):
    h, did = preparar(client, db)
    _retirar_r1(client, db, h, did)
    fila = estado(db)
    assert fila.ns == 1 and fila.ns_previo_retiro == 2  # el NS previo al retiro queda guardado
    assert abandonar(client, h, did)["ajuste_nivel"] is None  # 1.º desafío tras el retiro: NR
    j = abandonar(client, h, did)  # 2.º: NR → recaída
    assert j["ajuste_nivel"] == {
        "concepto": NOMBRE, "ns_anterior": 1, "ns_nuevo": 2,
        "motivo": MENSAJES["recaida"]["texto"].replace("{{concepto}}", NOMBRE),
    }
    assert [m["tipo"] for m in j["mensajes"]] == ["recaida"]
    fila = estado(db)
    assert fila.ns == 2 and fila.ns_previo_retiro is None and fila.pausa_retiros_restante == 3
    assert fila.desafios_desde_cambio == 0 and fila.ns_maximo_historico == 2
    assert list(db.scalars(select(HistorialNivel.regla).order_by(HistorialNivel.id))) == ["R1", "R3"]
    ev = db.scalar(select(EventoMotor).where(EventoMotor.regla == "R3"))
    assert (ev.ns_antes, ev.ns_despues, ev.resultado) == (1, 2, "cambio") and ev.indicadores["pausa_retiros"] == 0  # pausa vigente al evaluar


def test_recaida_tras_retiro_acelerado_r2_vuelve_a_3(client, db):
    h, did = preparar(client, db)
    poner_ns(db, 3)
    assert resolver(client, h, did)["ajuste_nivel"] is None
    assert resolver(client, h, did)["ajuste_nivel"] is None
    j = resolver(client, h, did)
    assert (j["ajuste_nivel"]["ns_anterior"], j["ajuste_nivel"]["ns_nuevo"]) == (3, 1)  # R2
    assert estado(db).ns_previo_retiro == 3
    assert abandonar(client, h, did)["ajuste_nivel"] is None
    j = abandonar(client, h, did)
    assert (j["ajuste_nivel"]["ns_anterior"], j["ajuste_nivel"]["ns_nuevo"]) == (1, 3)
    assert estado(db).ns == 3 and estado(db).pausa_retiros_restante == 3


def test_sin_recaida_si_uno_de_los_dos_desafios_siguientes_es_exitoso(client, db):
    h, did = preparar(client, db)
    _retirar_r1(client, db, h, did)
    assert resolver_con_error(client, h, did)["ajuste_nivel"] is None  # SA
    assert abandonar(client, h, did)["ajuste_nivel"] is None  # NR
    assert estado(db).ns == 1


def test_la_pausa_bloquea_r1_durante_3_desafios_y_despues_se_levanta(client, db):
    h, did = preparar(client, db)
    _retirar_r1(client, db, h, did)
    abandonar(client, h, did)
    assert abandonar(client, h, did)["ajuste_nivel"]["ns_nuevo"] == 2  # recaída: pausa de 3
    for restante in (2, 1, 0):  # 3 desafíos que habrían retirado (3 SA con 2 envíos) y no retiran
        assert resolver_con_error(client, h, did)["ajuste_nivel"] is None
        assert estado(db).pausa_retiros_restante == restante and estado(db).ns == 2
    j = resolver_con_error(client, h, did)  # 4.º: la pausa terminó
    assert (j["ajuste_nivel"]["ns_anterior"], j["ajuste_nivel"]["ns_nuevo"]) == (2, 1)
    assert list(db.scalars(select(HistorialNivel.regla).order_by(HistorialNivel.id))) == ["R1", "R3", "R1"]


def test_la_pausa_bloquea_tambien_r2(client, db):
    h, did = preparar(client, db)
    poner_ns(db, 3)
    for _ in range(2):
        resolver(client, h, did)
    resolver(client, h, did)  # R2: 3 → 1
    abandonar(client, h, did)
    assert abandonar(client, h, did)["ajuste_nivel"]["ns_nuevo"] == 3  # recaída
    for _ in range(3):  # 3 SA limpios que activarían R2 (y R1): pausados
        assert resolver(client, h, did)["ajuste_nivel"] is None
    assert estado(db).ns == 3
    assert resolver(client, h, did)["ajuste_nivel"]["ns_nuevo"] == 1  # pausa terminada: R2 retira 2


def test_el_retiro_se_identifica_por_historial_niveles_con_regla_r1_o_r2(client, db):
    h, did = preparar(client, db)
    poner_ns(db, 1)
    fila = estado(db)
    fila.ns_previo_retiro = 2
    db.commit()
    poner_historial(db, 2, 1, "R5")  # el último cambio no fue un retiro: R3 no corresponde
    abandonar(client, h, did)
    assert abandonar(client, h, did)["ajuste_nivel"] is None
    assert estado(db).ns == 1


# ---------- R12 integración ----------
def _dos_desafios(client, db):
    registrar(client)
    h = cabecera(token_de(client))
    return h, crear_desafio(db, "filtrado", "D1", "Uno"), crear_desafio(db, "filtrado", "D2", "Dos")


def _resolver_ya_iniciado(client, h, did):
    return client.post(f"{API}/desafios/{did}/intentos", json={"codigo": SOLUCION}, headers=h).json()


def test_iniciar_una_dificultad_mayor_sube_el_ns_de_0_a_1_y_pausa_los_retiros(client, db):
    h, d1, d2 = _dos_desafios(client, db)
    poner_ns(db, 0)
    j = client.post(f"{API}/desafios/{d1}/iniciar", headers=h).json()
    assert j["ajuste_nivel"] is None and j["mensajes"] == []  # el primero del concepto no es un cambio
    _resolver_ya_iniciado(client, h, d1)
    j = client.post(f"{API}/desafios/{d2}/iniciar", headers=h).json()
    assert j["ajuste_nivel"] == {
        "concepto": NOMBRE, "ns_anterior": 0, "ns_nuevo": 1,
        "motivo": MENSAJES["cambio_dificultad"]["texto"].replace("{{concepto}}", NOMBRE),
    }
    assert [m["tipo"] for m in j["mensajes"]] == ["cambio_dificultad"]
    fila = estado(db)
    assert fila.ns == 1 and fila.pausa_retiros_restante == 3 and fila.desafios_desde_cambio == 0
    assert list(db.scalars(select(HistorialNivel.regla))) == ["R12"]
    ev = db.scalar(select(EventoMotor).where(EventoMotor.regla == "R12"))
    assert (ev.ns_antes, ev.ns_despues, ev.resultado) == (0, 1, "cambio")
    # reanudar el mismo desafío no repite la regla
    assert client.post(f"{API}/desafios/{d2}/iniciar", headers=h).json()["ajuste_nivel"] is None
    assert db.scalar(select(EventoMotor).where(EventoMotor.regla == "R12", EventoMotor.id != ev.id)) is None


def test_r12_pausa_r2_tres_desafios_y_luego_retira(client, db):
    h, d1, d2 = _dos_desafios(client, db)
    poner_ns(db, 0)
    client.post(f"{API}/desafios/{d1}/iniciar", headers=h)
    _resolver_ya_iniciado(client, h, d1)
    client.post(f"{API}/desafios/{d2}/iniciar", headers=h)  # R12: NS 1, pausa 3
    assert _resolver_ya_iniciado(client, h, d2)["ajuste_nivel"] is None  # 1.º de la pausa
    assert resolver(client, h, d2)["ajuste_nivel"] is None  # 2.º
    assert resolver(client, h, d2)["ajuste_nivel"] is None  # 3.º: 3 SA limpios, pero R2 está pausada
    assert estado(db).ns == 1 and estado(db).pausa_retiros_restante == 0
    j = resolver(client, h, d2)  # 4.º: sin pausa
    assert (j["ajuste_nivel"]["ns_anterior"], j["ajuste_nivel"]["ns_nuevo"]) == (1, 0)


def test_r12_con_ns_mayor_a_1_no_cambia_el_ns_pero_si_pausa(client, db):
    h, d1, d2 = _dos_desafios(client, db)
    poner_ns(db, 2)
    client.post(f"{API}/desafios/{d1}/iniciar", headers=h)
    _resolver_ya_iniciado(client, h, d1)
    j = client.post(f"{API}/desafios/{d2}/iniciar", headers=h).json()
    assert j["ajuste_nivel"] is None and j["mensajes"] == []
    fila = estado(db)
    assert fila.ns == 2 and fila.pausa_retiros_restante == 3
    assert db.scalar(select(HistorialNivel)) is None  # sin cambio de NS no hay fila de historial
    ev = db.scalar(select(EventoMotor).where(EventoMotor.regla == "R12"))
    assert ev.resultado == "mantiene"


def test_r12_sin_fila_de_ns_crea_la_para_guardar_la_pausa_sin_reiniciar_la_ventana(client, db):
    h, d1, d2 = _dos_desafios(client, db)
    client.post(f"{API}/desafios/{d1}/iniciar", headers=h)
    _resolver_ya_iniciado(client, h, d1)
    client.post(f"{API}/desafios/{d2}/iniciar", headers=h)
    fila = estado(db)
    assert fila.ns == 1 and fila.pausa_retiros_restante == 3
    assert fila.ultimo_cambio_en <= ana(db).creado_en + timedelta(seconds=1)  # el cierre de D1 sigue en la ventana


def test_r12_no_corresponde_con_igual_o_menor_dificultad(client, db):
    h, d1, d2 = _dos_desafios(client, db)
    poner_ns(db, 0)
    client.post(f"{API}/desafios/{d2}/iniciar", headers=h)
    _resolver_ya_iniciado(client, h, d2)  # lo más alto cerrado: D2
    assert client.post(f"{API}/desafios/{d1}/iniciar", headers=h).json()["ajuste_nivel"] is None  # D1 < D2
    assert estado(db).ns == 0 and not estado(db).pausa_retiros_restante
    assert db.scalar(select(EventoMotor).where(EventoMotor.regla == "R12")) is None


def test_un_fallo_del_motor_no_rompe_el_inicio_del_desafio(client, db, monkeypatch):
    h, d1, d2 = _dos_desafios(client, db)
    from app.modules.desafios import hooks

    def falla(*_a, **_k):
        raise RuntimeError("motor caído")

    monkeypatch.setattr(hooks, "al_iniciar_desafio", falla)
    r = client.post(f"{API}/desafios/{d1}/iniciar", headers=h)
    assert r.status_code == 200 and r.json()["ajuste_nivel"] is None


# ---------- R14 integración ----------
def _sesion_hace(db, did, dias, horas=0):
    fin = ahora_utc() - timedelta(days=dias, hours=horas)
    db.add(
        SesionDesafio(
            usuario_id=ana(db).id, desafio_id=did, inicio=fin - timedelta(seconds=30), fin=fin, estado="resuelto",
            resultado_cierre="SA", tiempo_activo_seg=30, tiempo_activo_origen="reloj",
        )
    )
    db.commit()


def _fila_ns(db, ns, maximo, codigo="filtrado"):
    db.add(NivelSoporte(usuario_id=ana(db).id, concepto_id=concepto(db, codigo).id, ns=ns, ns_maximo_historico=maximo))
    db.commit()


def _login_json(client):
    r = hacer_login(client)
    assert r.status_code == 200
    return r.json()


def test_14_dias_sin_actividad_suben_el_ns_y_el_login_devuelve_el_reenganche(client, db):
    h, did = preparar(client, db)
    _fila_ns(db, 1, 3)
    _sesion_hace(db, did, 15)
    j = _login_json(client)
    assert j["mensaje_motor"] == MENSAJES["reenganche"]["texto"].replace("{{concepto}}", NOMBRE)
    fila = estado(db)
    assert fila.ns == 2 and fila.ns_maximo_historico == 3 and fila.desafios_desde_cambio == 0
    h1 = db.scalar(select(HistorialNivel))
    assert (h1.regla, h1.ns_anterior, h1.ns_nuevo) == ("R14", 1, 2)
    ev = db.scalar(select(EventoMotor).where(EventoMotor.regla == "R14"))
    assert (ev.ns_antes, ev.ns_despues, ev.resultado) == (1, 2, "cambio") and ev.indicadores["dias_inactivo"] >= 15


def test_r14_se_aplica_una_sola_vez_por_periodo_de_inactividad(client, db):
    h, did = preparar(client, db)
    _fila_ns(db, 0, 3)
    _sesion_hace(db, did, 20)
    assert _login_json(client)["mensaje_motor"] is not None
    assert _login_json(client)["mensaje_motor"] is None  # 2.º inicio de sesión sin actividad nueva
    assert estado(db).ns == 1
    # Vuelve a practicar y luego pasan otros 15 días: se simula retrocediendo el evento anterior y la actividad nueva.
    for ev in db.scalars(select(EventoMotor).where(EventoMotor.regla == "R14")):
        ev.creado_en = ahora_utc() - timedelta(days=25)
    db.commit()
    _sesion_hace(db, did, 15)
    assert _login_json(client)["mensaje_motor"] is not None
    assert estado(db).ns == 2


def test_r14_con_13_dias_no_hace_nada_y_con_14_si(client, db):
    h, did = preparar(client, db)
    _fila_ns(db, 1, 3)
    _sesion_hace(db, did, 13, horas=23)
    j = _login_json(client)
    assert j["mensaje_motor"] is None and estado(db).ns == 1
    assert db.scalar(select(EventoMotor).where(EventoMotor.regla == "R14")) is None
    _sesion_hace(db, did, 14)  # la más reciente sigue siendo la de 13 días y 23 h: no cuenta
    assert _login_json(client)["mensaje_motor"] is None
    db.execute(SesionDesafio.__table__.delete())
    db.commit()
    _sesion_hace(db, did, 14)
    assert _login_json(client)["mensaje_motor"] is not None and estado(db).ns == 2


def test_r14_no_supera_el_maximo_historico_y_deja_constancia(client, db):
    h, did = preparar(client, db)
    _fila_ns(db, 2, 2)
    _sesion_hace(db, did, 30)
    assert _login_json(client)["mensaje_motor"] is None  # nada pudo subir: no hay reenganche
    assert estado(db).ns == 2 and db.scalar(select(HistorialNivel)) is None
    ev = db.scalar(select(EventoMotor).where(EventoMotor.regla == "R14"))
    assert ev.resultado == "mantiene" and ev.concepto_id is None
    assert _login_json(client)["mensaje_motor"] is None  # y no se vuelve a evaluar


def test_r14_sube_cada_concepto_con_margen_y_nombra_a_los_que_subieron(client, db):
    h, did = preparar(client, db)
    _fila_ns(db, 0, 2, "filtrado")
    _fila_ns(db, 1, 1, "ordenamiento")  # ya está en su máximo
    _fila_ns(db, 2, 3, "join")
    _sesion_hace(db, did, 16)
    j = _login_json(client)
    nombres = list(
        db.scalars(select(Concepto.nombre).where(Concepto.codigo.in_(("filtrado", "join"))).order_by(Concepto.id))
    )
    assert j["mensaje_motor"] == MENSAJES["reenganche"]["texto"].replace("{{concepto}}", " y ".join(nombres))
    assert [estado(db, k).ns for k in ("filtrado", "ordenamiento", "join")] == [1, 1, 3]
    assert sorted(db.scalars(select(HistorialNivel.regla))) == ["R14", "R14"]


def test_r14_sin_ninguna_sesion_no_hace_nada(client, db):
    registrar(client)
    _fila_ns(db, 0, 3)
    assert _login_json(client)["mensaje_motor"] is None
    assert estado(db).ns == 0


def test_r14_solo_para_estudiantes(client, db):
    registrar(client)
    ana(db).rol = "docente"
    db.commit()
    assert _login_json(client)["mensaje_motor"] is None


def test_el_login_no_falla_si_el_motor_falla(client, db, monkeypatch):
    h, did = preparar(client, db)
    _fila_ns(db, 1, 3)
    _sesion_hace(db, did, 20)
    from app.modules.motor_retiro import motor

    def falla(*_a, **_k):
        raise RuntimeError("reglas.json ilegible")

    monkeypatch.setattr(motor, "evaluar_inactividad", falla)
    r = hacer_login(client)
    assert r.status_code == 200 and r.json()["mensaje_motor"] is None and r.json()["access_token"]
    assert estado(db).ns == 1  # el NS se mantiene


def test_el_login_no_falla_si_falla_la_base_a_mitad_del_motor(client, db, monkeypatch):
    h, did = preparar(client, db)
    _fila_ns(db, 1, 3)
    _sesion_hace(db, did, 20)
    from app.modules.motor_retiro import motor

    original = motor._guardar_cambio_ns

    def a_medias(*a, **k):
        original(*a, **k)  # deja cambios sin confirmar y luego falla
        raise RuntimeError("fallo a mitad de la escritura")

    monkeypatch.setattr(motor, "_guardar_cambio_ns", a_medias)
    r = hacer_login(client)
    assert r.status_code == 200 and r.json()["mensaje_motor"] is None
    assert estado(db).ns == 1 and db.scalar(select(HistorialNivel)) is None  # nada quedó a medias


def test_el_login_sin_reenganche_conserva_su_respuesta(client):
    registrar(client)
    j = _login_json(client)
    assert j["mensaje_motor"] is None and j["usuario"]["correo"] == "ana@uni.edu" and j["token_type"] == "bearer"
