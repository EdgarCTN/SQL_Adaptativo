import copy
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.db import ahora_utc
from app.modules.auth.models import Usuario
from app.modules.desafios.models import Concepto, Desafio, Intento, SesionDesafio
from app.modules.linea_base.models import NivelSoporte
from app.modules.motor_retiro import motor
from app.modules.motor_retiro.contexto import construir_contexto
from app.modules.motor_retiro.models import EventoMotor, HistorialNivel
from app.modules.asistencia.config_llm import cargar_mensajes_fijos
from app.core.reglas import cargar_reglas
from conftest import API, cabecera, registrar, token_de
from test_desafios import SOLUCION, crear_desafio

MENSAJES = cargar_mensajes_fijos()["mensajes"]


@pytest.fixture(autouse=True)
def _sin_sembrados(client, db):
    db.execute(Desafio.__table__.delete())
    db.commit()


def preparar(client, db, concepto="filtrado"):
    registrar(client)
    return cabecera(token_de(client)), crear_desafio(db, concepto)


def ana(db):
    return db.scalar(select(Usuario).where(Usuario.correo == "ana@uni.edu"))


def concepto(db, codigo="filtrado"):
    return db.scalar(select(Concepto).where(Concepto.codigo == codigo))


def poner_ns(db, ns, codigo="filtrado"):
    db.add(NivelSoporte(usuario_id=ana(db).id, concepto_id=concepto(db, codigo).id, ns=ns, ns_maximo_historico=ns))
    db.commit()


def abandonar(client, h, did):
    client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    return client.post(f"{API}/desafios/{did}/abandonar", headers=h).json()


def resolver(client, h, did):
    client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    return client.post(f"{API}/desafios/{did}/intentos", json={"codigo": SOLUCION}, headers=h).json()


def resolver_con_error(client, h, did):
    """Un envío fallido y luego la solución: SA con 2 envíos (NI=2). R1 corresponde; R2 no (exige 1 intento por desafío)."""
    client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    client.post(f"{API}/desafios/{did}/intentos", json={"codigo": "SELECT titulo FROM libros"}, headers=h)
    return client.post(f"{API}/desafios/{did}/intentos", json={"codigo": SOLUCION}, headers=h).json()


def poner_historial(db, ns_anterior, ns_nuevo, regla, codigo="filtrado"):
    db.add(
        HistorialNivel(
            usuario_id=ana(db).id, concepto_id=concepto(db, codigo).id, ns_anterior=ns_anterior, ns_nuevo=ns_nuevo,
            regla=regla, motivo=f"{regla} de prueba",
        )
    )
    db.commit()


def primera_ayuda(client, h, did):
    client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    tipo = client.post(f"{API}/desafios/{did}/ayuda", json={}, headers=h).json()["tipo_ayuda"]
    client.post(f"{API}/desafios/{did}/abandonar", headers=h)  # cierra la sesión (cuenta como un NR más)
    return tipo


def estado(db, codigo="filtrado"):
    db.expire_all()
    return db.scalar(select(NivelSoporte).where(NivelSoporte.concepto_id == concepto(db, codigo).id))


# ---------- R5 ----------
def test_tres_abandonos_refuerzan_y_se_guarda_en_niveles_e_historial(client, db):
    h, did = preparar(client, db)
    assert abandonar(client, h, did)["ajuste_nivel"] is None
    assert abandonar(client, h, did)["ajuste_nivel"] is None
    j = abandonar(client, h, did)
    assert j["ajuste_nivel"] == {
        "concepto": "Filtrado (WHERE)", "ns_anterior": 1, "ns_nuevo": 2,
        "motivo": MENSAJES["refuerzo"]["texto"].replace("{{concepto}}", "Filtrado (WHERE)"),
    }
    fila = estado(db)
    assert fila.ns == 2 and fila.desafios_desde_cambio == 0 and fila.ns_maximo_historico == 2 and fila.ultimo_cambio_en
    h1 = db.scalar(select(HistorialNivel))
    assert (h1.ns_anterior, h1.ns_nuevo, h1.regla, h1.usuario_id) == (1, 2, "R5", ana(db).id)
    assert "TA=0.00" in h1.motivo and h1.creado_en is not None
    ev = list(db.scalars(select(EventoMotor).order_by(EventoMotor.id)))
    assert [(e.regla, e.resultado) for e in ev] == [("R4", "mantiene"), ("R4", "mantiene"), ("R5", "cambio")]
    assert "datos insuficientes" in ev[0].detalle and ev[2].ns_antes == 1 and ev[2].ns_despues == 2
    assert ev[2].indicadores["ta"] == 0.0 and ev[2].indicadores["resultado_sesion"] == "NR"


def test_integracion_la_primera_ayuda_del_siguiente_desafio_sigue_el_nuevo_ns_tras_subir(client, db):
    h, did = preparar(client, db)
    for _ in range(2):
        abandonar(client, h, did)
    assert abandonar(client, h, did)["ajuste_nivel"]["ns_nuevo"] == 2
    assert primera_ayuda(client, h, did) == "AY2"  # antes (NS1) habría sido AY1


# ---------- R1 ----------
def test_tres_resueltos_sin_ayuda_retiran_y_la_primera_ayuda_baja(client, db):
    h, did = preparar(client, db)
    poner_ns(db, 2)
    # Con 2 envíos por desafío no son «limpios»: R2 (1 intento cada uno) no se adelanta y retira R1.
    assert resolver_con_error(client, h, did)["ajuste_nivel"] is None
    assert resolver_con_error(client, h, did)["ajuste_nivel"] is None
    j = resolver_con_error(client, h, did)
    assert j["correcto"] and j["resultado_cierre"] == "SA"
    assert j["ajuste_nivel"] == {
        "concepto": "Filtrado (WHERE)", "ns_anterior": 2, "ns_nuevo": 1,
        "motivo": MENSAJES["retiro_automatico"]["texto"].replace("{{concepto}}", "Filtrado (WHERE)"),
    }
    fila = estado(db)
    assert fila.ns == 1 and fila.ns_maximo_historico == 2 and fila.desafios_desde_cambio == 0
    hist = db.scalar(select(HistorialNivel))
    assert (hist.ns_anterior, hist.ns_nuevo, hist.regla) == (2, 1, "R1")
    # el contador se reinició: los dos siguientes no vuelven a retirar
    assert resolver_con_error(client, h, did)["ajuste_nivel"] is None
    assert resolver_con_error(client, h, did)["ajuste_nivel"] is None
    assert estado(db).ns == 1
    # y la primera ayuda ahora es la del NS1
    client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    assert client.post(f"{API}/desafios/{did}/ayuda", json={}, headers=h).json()["tipo_ayuda"] == "AY1"


def test_r1_con_ns_en_cero_el_minimo(client, db):
    h, did = preparar(client, db)
    poner_ns(db, 1)
    for _ in range(2):
        resolver_con_error(client, h, did)
    assert resolver_con_error(client, h, did)["ajuste_nivel"]["ns_nuevo"] == 0
    assert estado(db).ns == 0
    for _ in range(3):
        j = resolver(client, h, did)
    assert j["ajuste_nivel"] is None and estado(db).ns == 0  # no baja de 0


def test_ns3_con_tres_abandonos_se_queda_en_3(client, db):
    h, did = preparar(client, db)
    poner_ns(db, 3)
    for _ in range(3):
        j = abandonar(client, h, did)
    assert j["ajuste_nivel"] is None and estado(db).ns == 3
    ultimo = db.scalars(select(EventoMotor).order_by(EventoMotor.id.desc())).first()
    assert (ultimo.regla, ultimo.resultado, ultimo.ns_despues) == ("R5", "mantiene", 3)
    assert db.scalar(select(HistorialNivel.id)) is None


def test_otro_concepto_no_cuenta_en_la_ventana(client, db):
    h, did = preparar(client, db)
    otro = crear_desafio(db, "join", "D2", "Otro")
    abandonar(client, h, did)
    abandonar(client, h, otro)
    assert abandonar(client, h, did)["ajuste_nivel"] is None  # solo 2 de filtrado
    assert abandonar(client, h, did)["ajuste_nivel"]["ns_nuevo"] == 2  # 3.º de filtrado


def test_la_ayuda_extra_baja_la_tasa_de_acierto(client, db):
    """Resueltos con AY1+AY2 son CE (no éxito): TA=0 → refuerzo, no retiro."""
    h, did = preparar(client, db)
    for i in range(3):
        client.post(f"{API}/desafios/{did}/iniciar", headers=h)
        client.post(f"{API}/desafios/{did}/ayuda", json={}, headers=h)
        client.post(f"{API}/desafios/{did}/intentos", json={"codigo": "SELECT titulo FROM libros"}, headers=h)
        client.post(f"{API}/desafios/{did}/ayuda", json={}, headers=h)  # AY2: más de lo previsto en NS1
        j = client.post(f"{API}/desafios/{did}/intentos", json={"codigo": SOLUCION}, headers=h).json()
        assert j["resultado_cierre"] == "CE"
    assert j["ajuste_nivel"]["ns_nuevo"] == 2


# ---------- Fallos: el cierre nunca se rompe ----------
@pytest.mark.parametrize("fallo", ["evaluar", "reglas", "base"])
def test_fallo_del_motor_mantiene_el_ns_y_el_desafio_se_cierra(client, db, monkeypatch, fallo):
    h, did = preparar(client, db)
    poner_ns(db, 2)
    if fallo == "evaluar":
        monkeypatch.setattr(motor, "evaluar", lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")))
    elif fallo == "reglas":
        monkeypatch.setattr(motor, "cargar_reglas", lambda: (_ for _ in ()).throw(OSError("reglas.json no se puede leer")))
    else:
        monkeypatch.setattr(motor, "construir_contexto", lambda *a, **k: (_ for _ in ()).throw(ValueError("tabla rota")))
    for _ in range(3):
        j = resolver(client, h, did)
        assert j["correcto"] and j["estado_sesion"] == "resuelto" and j["ajuste_nivel"] is None
    assert estado(db).ns == 2
    ses = list(db.scalars(select(SesionDesafio)))
    assert len(ses) == 3 and all(s.estado == "resuelto" and s.resultado_cierre == "SA" for s in ses)
    ev = list(db.scalars(select(EventoMotor)))
    assert len(ev) == 3 and all(e.resultado == "error" and e.ns_antes == 2 and e.ns_despues == 2 for e in ev)
    assert db.scalar(select(HistorialNivel.id)) is None
    assert any(x in ev[0].detalle for x in ("boom", "reglas.json", "tabla rota"))


def test_abandonar_tambien_sobrevive_al_fallo(client, db, monkeypatch):
    h, did = preparar(client, db)
    monkeypatch.setattr(motor, "evaluar", lambda ctx: (_ for _ in ()).throw(RuntimeError("boom")))
    j = abandonar(client, h, did)
    assert j["estado"] == "abandonado" and j["resultado_cierre"] == "NR" and j["ajuste_nivel"] is None


# ---------- Contexto: ventana y desafíos desde el último cambio ----------
def _sesion(db, uid, did, minutos_atras, resultado="SA", intentos=1, tiempo=30):
    fin = ahora_utc() - timedelta(minutes=minutos_atras)
    s = SesionDesafio(usuario_id=uid, desafio_id=did, inicio=fin - timedelta(seconds=tiempo), fin=fin,
                      estado="resuelto" if resultado != "NR" else "abandonado", resultado_cierre=resultado, tiempo_activo_seg=tiempo)
    db.add(s)
    db.commit()
    for n in range(1, intentos + 1):
        db.add(Intento(sesion_id=s.id, numero=n, codigo="x", correcto=n == intentos, resultado_obtenido={}))
    db.commit()
    return s


def test_la_ventana_toma_los_5_ultimos_cierres_posteriores_al_ultimo_cambio(client, db):
    registrar(client)
    uid = ana(db).id
    did, otro = crear_desafio(db, "filtrado"), crear_desafio(db, "join", "D2", "Otro")
    fila = NivelSoporte(usuario_id=uid, concepto_id=concepto(db).id, ns=2, ns_maximo_historico=2,
                        ultimo_cambio_en=ahora_utc() - timedelta(minutes=100))
    db.add(fila)
    db.commit()
    _sesion(db, uid, did, 200, "NR")  # anterior al cambio: no cuenta
    for i, r in enumerate(["CE", "SA", "CP", "SA", "NR", "SA", "CE"]):  # 7 posteriores (más antigua primero)
        _sesion(db, uid, did, 90 - i * 10, r, intentos=2 if r == "CE" else 1)
    _sesion(db, uid, otro, 5, "SA")  # otro concepto: no cuenta
    en_curso = SesionDesafio(usuario_id=uid, desafio_id=did, estado="en_curso")
    db.add(en_curso)
    db.commit()
    ultima = db.scalar(select(SesionDesafio).where(SesionDesafio.resultado_cierre.is_not(None)).order_by(SesionDesafio.fin.desc()))
    ctx = construir_contexto(db, ultima, db.get(Desafio, did), concepto(db), cargar_reglas())
    assert ctx.ns_actual == 2 and ctx.desafios_desde_cambio == 7
    assert [x.resultado for x in ctx.cierres_recientes] == ["CP", "SA", "NR", "SA", "CE"]  # 5 más recientes, orden cronológico
    assert ctx.cierres_recientes[-1].intentos == 2 and ctx.cierres_recientes[-1].tiempo_referencia_seg == 120
    assert ctx.indicadores.n == 5 and ctx.indicadores.ta == 0.6 and ctx.indicadores.ni == 1.0


def test_sin_registro_de_ns_se_usa_el_por_defecto_y_todos_los_cierres(client, db):
    registrar(client)
    uid = ana(db).id
    did = crear_desafio(db)
    s = _sesion(db, uid, did, 10, "SA")
    ctx = construir_contexto(db, s, db.get(Desafio, did), concepto(db), cargar_reglas())
    assert ctx.ns_actual == 1 and ctx.desafios_desde_cambio == 1


# ---------- R2 (entrega 5) ----------
def test_r2_tres_resueltos_limpios_bajan_dos_niveles_y_la_primera_ayuda_sigue_el_nuevo_ns(client, db):
    h, did = preparar(client, db)
    poner_ns(db, 2)
    assert resolver(client, h, did)["ajuste_nivel"] is None
    assert resolver(client, h, did)["ajuste_nivel"] is None
    j = resolver(client, h, did)
    assert j["resultado_cierre"] == "SA"
    assert j["ajuste_nivel"] == {
        "concepto": "Filtrado (WHERE)", "ns_anterior": 2, "ns_nuevo": 0,
        "motivo": MENSAJES["retiro_automatico"]["texto"].replace("{{concepto}}", "Filtrado (WHERE)"),
    }
    assert [(m["clave"], m["tipo"]) for m in j["mensajes"]] == [("retiro_automatico", "retiro")]
    fila = estado(db)
    assert fila.ns == 0 and fila.ns_maximo_historico == 2 and fila.desafios_desde_cambio == 0 and fila.ultimo_cambio_en
    hist = db.scalar(select(HistorialNivel))
    assert (hist.ns_anterior, hist.ns_nuevo, hist.regla) == (2, 0, "R2") and "R2" in hist.motivo
    ultimo = db.scalars(select(EventoMotor).order_by(EventoMotor.id.desc())).first()
    assert (ultimo.regla, ultimo.resultado, ultimo.ns_antes, ultimo.ns_despues) == ("R2", "cambio", 2, 0)
    assert primera_ayuda(client, h, did) == "AY1"  # en NS2 la primera ayuda habría sido AY2


def test_r2_con_una_ayuda_entre_los_tres_no_es_acelerado_y_retira_r1(client, db):
    """Un desafío con ayuda no es SA: los 3 últimos no son limpios; R1 (TA 1.0, NI 1) retira solo 1 nivel."""
    h, did = preparar(client, db)
    poner_ns(db, 2)
    resolver(client, h, did)
    resolver(client, h, did)
    client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    assert client.post(f"{API}/desafios/{did}/ayuda", json={}, headers=h).json()["tipo_ayuda"] == "AY2"
    j = client.post(f"{API}/desafios/{did}/intentos", json={"codigo": SOLUCION}, headers=h).json()
    assert j["resultado_cierre"] == "CP" and j["ajuste_nivel"]["ns_nuevo"] == 1
    assert db.scalar(select(HistorialNivel)).regla == "R1"


# ---------- R6 (entrega 5) ----------
def test_r6_a_ns3_con_ta_baja_y_refuerzos_previos_deriva_sin_cambiar_el_ns(client, db):
    h, did = preparar(client, db)
    for _ in range(2):
        abandonar(client, h, did)
    assert abandonar(client, h, did)["ajuste_nivel"]["ns_nuevo"] == 2  # R5 (refuerzo previo 1)
    for _ in range(2):
        abandonar(client, h, did)
    assert abandonar(client, h, did)["ajuste_nivel"]["ns_nuevo"] == 3  # R5 (refuerzo previo 2)
    for _ in range(2):  # con NS3 aún no hay 3 desafíos desde el cambio
        assert abandonar(client, h, did)["mensajes"] == []
    j = abandonar(client, h, did)  # 3.º desde el cambio, TA 0.00: R6 (a); `filtrado` no tiene prerrequisito
    assert j["ajuste_nivel"] is None and estado(db).ns == 3
    assert [(m["clave"], m["tipo"], m["enlace"], m["texto"]) for m in j["mensajes"]] == [
        ("estancamiento_derivar", "estancamiento", None, MENSAJES["estancamiento_derivar"]["texto"])
    ]
    ev = db.scalars(select(EventoMotor).order_by(EventoMotor.id.desc())).first()
    assert (ev.regla, ev.resultado, ev.ns_antes, ev.ns_despues) == ("R6", "mantiene", 3, 3)
    assert ev.indicadores["r6_condicion"] == "a" and ev.indicadores["prerrequisito"] is None and "R6 estancamiento (a)" in ev.detalle
    assert len(list(db.scalars(select(HistorialNivel)))) == 2  # R6 no cambia el NS: no deja fila en historial_niveles


@pytest.mark.parametrize(
    "ns_previo,clave,enlace",
    [
        (None, "estancamiento_derivar", None),  # sin fila en niveles_soporte: NS por defecto 1 = dominado
        (0, "estancamiento_derivar", None),
        (1, "estancamiento_derivar", None),
        (2, "estancamiento_previo_sin_dominar", "/desafios?concepto=filtrado"),
        (3, "estancamiento_previo_sin_dominar", "/desafios?concepto=filtrado"),
    ],
)
def test_r6_a_segun_el_ns_del_prerrequisito(client, db, ns_previo, clave, enlace):
    h, did = preparar(client, db, "join")  # join depende de filtrado (mapa PROVISIONAL de prerrequisitos)
    poner_ns(db, 3, "join")
    poner_historial(db, 2, 3, "R5", "join")
    if ns_previo is not None:
        poner_ns(db, ns_previo, "filtrado")
    for _ in range(2):
        assert abandonar(client, h, did)["mensajes"] == []
    j = abandonar(client, h, did)
    assert [(m["clave"], m["enlace"]) for m in j["mensajes"]] == [(clave, enlace)]
    if enlace:
        assert "Filtrado (WHERE)" in j["mensajes"][0]["texto"]  # {{concepto_previo}} reemplazado
    assert estado(db, "join").ns == 3
    ev = db.scalars(select(EventoMotor).order_by(EventoMotor.id.desc())).first()
    assert ev.regla == "R6" and ev.indicadores["prerrequisito"] == "filtrado"


@pytest.mark.parametrize("regla,cuenta", [("R5", True), ("R8", True), ("R12", False), ("R14", False), ("R3", False)])
def test_r6_a_solo_cuentan_como_refuerzo_las_reglas_de_reglas_json(client, db, regla, cuenta):
    """Decisión PROVISIONAL: cuentan R5 y R8; R12, R14 y R3 no. Sin refuerzo previo NS3 + TA baja queda en R5."""
    h, did = preparar(client, db)
    poner_ns(db, 3)
    poner_historial(db, 2, 3, regla)
    for _ in range(2):
        abandonar(client, h, did)
    j = abandonar(client, h, did)
    ev = db.scalars(select(EventoMotor).order_by(EventoMotor.id.desc())).first()
    if cuenta:
        assert ev.regla == "R6" and [m["clave"] for m in j["mensajes"]] == ["estancamiento_derivar"]
    else:
        assert ev.regla == "R5" and ev.resultado == "mantiene" and j["mensajes"] == [] and j["ajuste_nivel"] is None


def test_la_lista_de_refuerzo_previo_se_lee_de_reglas_json_y_acota_por_estudiante_y_concepto(client, db):
    registrar(client)
    uid = ana(db).id
    did = crear_desafio(db, "join", "D2", "Unir")
    poner_ns(db, 3, "join")
    for regla in ("R5", "R8", "R12", "R14", "R3"):
        poner_historial(db, 2, 3, regla, "join")
    poner_historial(db, 2, 3, "R5", "filtrado")  # otro concepto: no cuenta
    s = _sesion(db, uid, did, 5, "NR")

    def refuerzos(cfg):
        return construir_contexto(db, s, db.get(Desafio, did), concepto(db, "join"), cfg).refuerzos_previos

    base = cargar_reglas()
    assert base["r6_estancamiento"]["reglas_que_cuentan_como_refuerzo"] == ["R5", "R8"]
    assert base["r6_estancamiento"]["provisional"] is True
    assert refuerzos(base) == 2
    cfg = copy.deepcopy(base)
    cfg["r6_estancamiento"]["reglas_que_cuentan_como_refuerzo"] = ["R12", "R14", "R3"]
    assert refuerzos(cfg) == 3
    cfg["r6_estancamiento"]["reglas_que_cuentan_como_refuerzo"] = []
    assert refuerzos(cfg) == 0


def test_el_contexto_trae_los_datos_de_r6_solo_con_ns3_y_el_prerrequisito_vigente(client, db):
    registrar(client)
    uid = ana(db).id
    did = crear_desafio(db, "join", "D2", "Unir")
    poner_ns(db, 2, "join")
    poner_historial(db, 1, 2, "R5", "join")
    s = _sesion(db, uid, did, 5, "NR")
    ctx = construir_contexto(db, s, db.get(Desafio, did), concepto(db, "join"), cargar_reglas())
    assert (ctx.refuerzos_previos, ctx.prerrequisito_codigo, ctx.prerrequisito_ns) == (0, None, None)  # NS2: no se consulta
    estado(db, "join").ns = 3
    db.commit()
    ctx = construir_contexto(db, s, db.get(Desafio, did), concepto(db, "join"), cargar_reglas())
    assert (ctx.refuerzos_previos, ctx.prerrequisito_codigo, ctx.prerrequisito_nombre) == (1, "filtrado", "Filtrado (WHERE)")
    assert ctx.prerrequisito_ns == 1  # sin registro: NS por defecto
    poner_ns(db, 2, "filtrado")
    ctx = construir_contexto(db, s, db.get(Desafio, did), concepto(db, "join"), cargar_reglas())
    assert ctx.prerrequisito_ns == 2


def test_reglas_json_sin_la_lista_de_r6_no_rompe_el_cierre(client, db):
    h, did = preparar(client, db)
    poner_ns(db, 3)
    abandonar(client, h, did)
    cfg = copy.deepcopy(cargar_reglas())
    del cfg["r6_estancamiento"]["reglas_que_cuentan_como_refuerzo"]
    r = motor.cerrar_desafio_con_mensajes(db, db.scalar(select(SesionDesafio)), cfg)
    assert r.ajuste is None and r.mensajes == ()
    ev = db.scalars(select(EventoMotor).order_by(EventoMotor.id.desc())).first()
    assert ev.resultado == "error" and "reglas_que_cuentan_como_refuerzo" in ev.detalle and estado(db).ns == 3
