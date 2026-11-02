"""Entrega 8: R9 dependencia, R10 ensayo y error, R11 sobreconfianza y oferta de ayuda (Tabla 11, preferencia 3.3)."""
import re
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from sqlalchemy import select

from app.core.db import ahora_utc
from app.core.reglas import cargar_reglas
from app.modules.analitica.extractores import cierres_del_concepto, pedidos_df
from app.modules.analitica.indicadores import proporcion_pedidos_directos
from app.modules.asistencia.config_llm import cargar_mensajes_fijos
from app.modules.asistencia.decision import decidir_ayuda
from app.modules.asistencia.models import SolicitudAyuda
from app.modules.asistencia.oferta import motivo_de_oferta
from app.modules.asistencia.preferencias import preferencia_ayuda
from app.modules.desafios.models import Desafio, Intento, SesionDesafio
from app.modules.linea_base.models import LineaBaseCuestionario, LineaBaseResultado
from app.modules.motor_retiro.contexto import ContextoRegla
from app.modules.motor_retiro.dependencia import cumple_criterio, estado_dependencia
from app.modules.motor_retiro.ensayo_error import es_ensayo_error
from app.modules.motor_retiro.indicadores import CierreReciente
from app.modules.motor_retiro.models import EventoMotor, Verificacion
from app.modules.motor_retiro.reglas.r1_retiro_estandar import R1RetiroEstandar
from conftest import API, cabecera, registrar, token_de
from test_asistencia_api import Falso, falso  # noqa: F401  (falso es un fixture)
from test_desafios import SOLUCION, crear_desafio
from test_motor_integracion import ana, concepto, estado, poner_ns

REGLAS = cargar_reglas()
MENSAJES = cargar_mensajes_fijos()["mensajes"]
MALA = "SELECT titulo FROM libros"
SOBRECONFIANZA = {"r11": {"sobreconfianza": True, "errores_confianza_alta": 2}}
DEPENDENCIA = {"r9": {"riesgo": True, "senales_cumplidas": 2}}


@pytest.fixture(autouse=True)
def _sin_sembrados(client, db):
    db.execute(Desafio.__table__.delete())
    db.commit()


# ---------- utilidades ----------
def preparar(client, db, concepto_codigo="filtrado"):
    registrar(client)
    return cabecera(token_de(client)), crear_desafio(db, concepto_codigo)


def poner_linea_base(db, prefs=None, banderas=None):
    db.add(
        LineaBaseResultado(
            usuario_id=ana(db).id, cuestionario_id=db.scalar(select(LineaBaseCuestionario.id)),
            preferencias=prefs or {}, banderas_iniciales=banderas or {},
        )
    )
    db.commit()


def iniciar(client, h, did):
    return client.post(f"{API}/desafios/{did}/iniciar", headers=h)


def enviar(client, h, did, codigo=MALA):
    r = client.post(f"{API}/desafios/{did}/intentos", json={"codigo": codigo}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def pedir_ayuda(client, h, did):
    return client.post(f"{API}/desafios/{did}/ayuda", json={}, headers=h)


def sesion_en_curso(db):
    db.expire_all()
    return db.scalar(select(SesionDesafio).where(SesionDesafio.estado == "en_curso"))


def eventos(db, regla):
    db.expire_all()
    return list(db.scalars(select(EventoMotor).where(EventoMotor.regla == regla).order_by(EventoMotor.id)))


def cerrada(db, did, resultado="CP", t=0):
    """Sesión ya cerrada del estudiante con tiempo medido (sin pasar por el motor)."""
    fin = ahora_utc() + timedelta(seconds=t)
    s = SesionDesafio(
        usuario_id=ana(db).id, desafio_id=did, inicio=fin - timedelta(seconds=30), fin=fin, estado="resuelto",
        resultado_cierre=resultado, tiempo_activo_seg=30, tiempo_activo_origen="latidos",
    )
    db.add(s)
    db.commit()
    return s


def solicitud(db, sesion, tipo="AY1", solicitado=None, previos=3, sola=False):
    db.add(
        SolicitudAyuda(
            sesion_id=sesion.id, usuario_id=sesion.usuario_id, desafio_id=sesion.desafio_id, tipo_ayuda=tipo,
            proveedor="mock", texto_entregado="t", mostrada_sola=sola, tipo_solicitado=solicitado or tipo,
            intentos_previos=previos,
        )
    )
    db.commit()


# ======================= R9: criterio y mínimos =======================
CASOS_R9 = [  # (ua, pedidos directos, ¿dependencia?)
    (0.8, None, True), (0.79, None, False), (1.0, 0.0, True), (None, 0.5, True), (0.2, 0.49, False),
    (0.0, 0.5, True), (None, None, False), (0.8, 0.5, True),
]


@pytest.mark.parametrize("ua,pedidos,esperado", CASOS_R9)
def test_r9_tabla_del_criterio_dinamico(ua, pedidos, esperado):
    assert cumple_criterio(ua, pedidos, REGLAS["r9_dependencia"]) is esperado


def test_r9_proporcion_de_pedidos_directos_usa_el_tipo_solicitado():
    df = pd.DataFrame(
        {
            "sesion_id": [1, 2, 3, 4], "tipo_ayuda": ["AY1", "AY1", "AY3", "AY2"],
            "tipo_solicitado": ["AY3", "AY1", "AY4", None], "intentos_previos": [0, 3, 1, 0],
        }
    )
    # AY3 con 0 previos (sí) · AY1 (no) · AY4 con 1 previo (sí) · sin tipo solicitado se usa el entregado AY2 (no)
    assert proporcion_pedidos_directos(df, ("AY3", "AY4"), 1) == 0.5
    df.loc[2, "intentos_previos"] = 2  # con 2 envíos previos ya no es directo
    assert proporcion_pedidos_directos(df, ("AY3", "AY4"), 1) == 0.25
    assert proporcion_pedidos_directos(df.iloc[0:0], ("AY3", "AY4"), 1) is None


# (NS, fallos, previas, desde_ultima, dependencia, tipo esperado)
CASOS_MINIMOS = [
    (3, 2, [], 0, False, "AY3"), (3, 2, [], 0, True, "AY2"),  # AY3 pide 2 fallos; con R9, 3
    (3, 3, [], 0, True, "AY3"), (3, 1, [], 0, True, "AY2"),  # sin el mínimo, el tipo inmediatamente inferior
    (2, 2, [], 0, True, "AY2"),  # AY1 y AY2 no tienen mínimo
    (3, 3, ["AY3"], 1, False, "AY4"), (3, 3, ["AY3"], 1, True, "AY3"),  # AY4 pide 3 fallos; con R9, 4
    (3, 4, ["AY3"], 1, True, "AY4"),
]


@pytest.mark.parametrize("ns,fallos,previas,desde,dep,esperado", CASOS_MINIMOS)
def test_r9_sube_en_uno_el_minimo_de_ay3_y_ay4(ns, fallos, previas, desde, dep, esperado):
    d = decidir_ayuda(ns, fallos, previas, desde, dependencia=dep)
    assert d.tipo == esperado


def test_r9_el_incremento_sale_de_reglas_json():
    reglas = {**REGLAS, "ayuda_en_desafio": {**REGLAS["ayuda_en_desafio"], "incremento_minimos_por_dependencia": 2}}
    assert decidir_ayuda(3, 3, [], 0, reglas, dependencia=True).tipo == "AY2"  # AY3 ahora pide 4 fallos
    assert decidir_ayuda(3, 4, [], 0, reglas, dependencia=True).tipo == "AY3"


def test_r9_la_decision_recuerda_el_tipo_solicitado_aunque_se_degrade():
    d = decidir_ayuda(3, 0, [], 0)
    assert (d.tipo, d.solicitado, d.degradada) == ("AY2", "AY3", True)


# ======================= R9: estado por concepto =======================
def test_r9_bandera_inicial_rige_hasta_tener_tres_desafios(client, db):
    h, did = preparar(client, db)
    poner_linea_base(db, banderas=DEPENDENCIA)
    e = estado_dependencia(db, ana(db).id, concepto(db).id)
    assert (e.activa, e.origen, e.evaluable, e.n) == (True, "inicial", False, 0)
    cerrada(db, did, "SA"), cerrada(db, did, "SA")
    assert estado_dependencia(db, ana(db).id, concepto(db).id).origen == "inicial"


def test_r9_con_tres_desafios_la_ventana_reemplaza_a_la_inicial(client, db):
    h, did = preparar(client, db)
    poner_linea_base(db, banderas=DEPENDENCIA)
    for _ in range(3):
        cerrada(db, did, "SA")  # sin ayuda: UA = 0
    e = estado_dependencia(db, ana(db).id, concepto(db).id)
    assert (e.activa, e.origen, e.evaluable, e.inicial, e.ua) == (False, "ninguno", True, True, 0.0)


def test_r9_dinamica_por_ua_de_la_capa_analitica(client, db):
    h, did = preparar(client, db)
    for _ in range(3):
        s = cerrada(db, did, "CP")
        solicitud(db, s, "AY1", previos=3)  # ayuda pedida con varios envíos: solo cuenta la UA
    e = estado_dependencia(db, ana(db).id, concepto(db).id)
    assert (e.activa, e.origen, e.ua, e.pedidos_directos) == (True, "dinamica", 1.0, 0.0)


def test_r9_dinamica_por_pedidos_directos_de_ay3_o_ay4(client, db):
    h, did = preparar(client, db)
    solicitud(db, cerrada(db, did, "CE"), "AY1", solicitado="AY3", previos=0)  # pidió la solución parcial sin intentar
    cerrada(db, did, "SA"), cerrada(db, did, "SA")
    e = estado_dependencia(db, ana(db).id, concepto(db).id)
    assert round(e.ua, 2) == 0.33 and e.pedidos_directos == 1.0 and e.activa and e.origen == "dinamica"


def test_r9_las_ayudas_mostradas_solas_no_cuentan_ni_para_ua_ni_para_r9(client, db):
    h, did = preparar(client, db)
    for _ in range(3):
        solicitud(db, cerrada(db, did, "CP"), "AY1", solicitado="AY3", previos=0, sola=True)
    e = estado_dependencia(db, ana(db).id, concepto(db).id)
    assert (e.activa, e.ua, e.pedidos_directos) == (False, 0.0, None)
    df = cierres_del_concepto(db, ana(db).id, concepto(db).id)
    assert not df["uso_ayuda"].any()
    assert pedidos_df(db, [int(s) for s in df["sesion_id"]]).empty


def test_r9_una_sesion_con_ayuda_sola_y_otra_pedida_cuenta_como_uso(client, db):
    h, did = preparar(client, db)
    s = cerrada(db, did, "CE")
    solicitud(db, s, "AY1", sola=True)
    solicitud(db, s, "AY2", previos=3)
    assert bool(cierres_del_concepto(db, ana(db).id, concepto(db).id)["uso_ayuda"].iloc[0]) is True


def test_r9_en_el_desafio_sube_el_minimo_y_manda_la_bandera_al_prompt(client, db, falso):
    h, did = preparar(client, db)
    poner_linea_base(db, banderas=DEPENDENCIA)
    poner_ns(db, 3)
    iniciar(client, h, did)
    enviar(client, h, did), enviar(client, h, did)  # 2 fallos: sin R9 la primera ayuda sería AY3
    j = pedir_ayuda(client, h, did).json()
    assert j["tipo_ayuda"] == "AY2" and "inténtalo" not in (j["sugerencia"] or "") and j["sugerencia"]
    s = db.scalar(select(SolicitudAyuda))
    assert (s.tipo_solicitado, s.intentos_previos, s.mostrada_sola) == ("AY3", 2, False)
    p = falso.llamadas[0]
    assert "[BANDERA: dependencia]" in p.prompt_sistema and "[BANDERA: sobreconfianza]" not in p.prompt_sistema
    assert "<banderas>dependencia</banderas>" in p.mensaje_usuario
    enviar(client, h, did)  # 3 fallos: ya cumple el mínimo de AY3 con R9
    assert pedir_ayuda(client, h, did).json()["tipo_ayuda"] == "AY3"
    ev = eventos(db, "R9")
    assert len(ev) == 1 and ev[0].indicadores["origen"] == "inicial" and ev[0].resultado == "mantiene"  # una por desafío


def test_r9_sin_bandera_la_primera_ayuda_sigue_igual(client, db, falso):
    h, did = preparar(client, db)
    poner_ns(db, 3)
    iniciar(client, h, did)
    enviar(client, h, did), enviar(client, h, did)
    assert pedir_ayuda(client, h, did).json()["tipo_ayuda"] == "AY3"
    assert "[BANDERA" not in falso.llamadas[0].prompt_sistema and eventos(db, "R9") == []


# ======================= R11: sobreconfianza =======================
def _ctx(resultados, sobreconfianza):
    cierres = [CierreReciente(r, 1, 10, 120, r != "SA") for r in resultados]
    return ContextoRegla(
        usuario_id=1, concepto_id=1, concepto_nombre="Filtrado", ns_actual=1, sesion_id=1, resultado_sesion=resultados[-1],
        cierres_recientes=cierres, desafios_desde_cambio=len(cierres), config=REGLAS, sobreconfianza=sobreconfianza,
    )


CASOS_R11 = [  # (resultados de la ventana, bandera, ¿R1 aplica?, ¿R11 la bloqueó?)
    (["SA", "SA", "SA"], True, True, False),
    (["SA", "CP", "SA"], True, False, True),
    (["SA", "CP", "SA"], False, True, False),
    (["CP", "SA", "SA"], True, True, False),
    (["SA", "SA", "CP"], True, False, True),
    (["CP", "CP", "CP"], True, False, True),
    (["CP", "CP", "CP"], False, True, False),
    (["SA", "CP", "SA", "SA"], True, True, False),
]


@pytest.mark.parametrize("resultados,bandera,aplica,bloqueo", CASOS_R11)
def test_r11_tabla_r1_exige_los_dos_ultimos_en_sa(resultados, bandera, aplica, bloqueo):
    ctx = _ctx(resultados, bandera)
    assert R1RetiroEstandar().aplica(ctx) is aplica
    assert R1RetiroEstandar.bloqueada_por_r11(ctx) is bloqueo


def test_r11_si_el_criterio_de_r1_no_se_cumple_no_se_dice_que_r11_bloqueo():
    ctx = _ctx(["CE", "CE", "CE"], True)
    assert R1RetiroEstandar().aplica(ctx) is False and R1RetiroEstandar.bloqueada_por_r11(ctx) is False


def _secuencia_sa_cp_sa(client, did):
    """SA, CP (con una pista AY1 prevista en NS 1) y SA."""
    res = []
    h = cabecera(token_de(client))
    iniciar(client, h, did)
    res.append(enviar(client, h, did, SOLUCION))
    iniciar(client, h, did)
    assert pedir_ayuda(client, h, did).json()["tipo_ayuda"] == "AY1"
    res.append(enviar(client, h, did, SOLUCION))
    iniciar(client, h, did)
    res.append(enviar(client, h, did, SOLUCION))
    return h, res


def test_r11_integracion_el_retiro_espera_a_los_dos_ultimos_sa(client, db, falso):
    h, did = preparar(client, db)
    poner_linea_base(db, banderas=SOBRECONFIANZA)
    poner_ns(db, 1)
    h, res = _secuencia_sa_cp_sa(client, did)
    assert [r["resultado_cierre"] for r in res] == ["SA", "CP", "SA"]
    assert res[2]["ajuste_nivel"] is None and estado(db).ns == 1  # R1 se cumplía, R11 lo frena
    ev11 = [e for e in eventos(db, "R11") if e.indicadores.get("ultimos")]
    assert len(ev11) == 1 and ev11[0].ns_antes == ev11[0].ns_despues == 1
    iniciar(client, h, did)
    r4 = enviar(client, h, did, SOLUCION)  # ahora los 2 últimos son SA
    assert r4["ajuste_nivel"]["ns_nuevo"] == 0 and estado(db).ns == 0


def test_r11_sin_la_bandera_el_mismo_historial_retira_enseguida(client, db, falso):
    h, did = preparar(client, db)
    poner_ns(db, 1)
    h, res = _secuencia_sa_cp_sa(client, did)
    assert res[2]["ajuste_nivel"]["ns_nuevo"] == 0 and eventos(db, "R11") == []


def test_r11_tras_un_acierto_se_muestra_el_mensaje_y_se_registra(client, db):
    h, did = preparar(client, db)
    poner_linea_base(db, banderas=SOBRECONFIANZA)
    iniciar(client, h, did)
    fallo = enviar(client, h, did)
    assert all(m["tipo"] != "sobreconfianza" for m in fallo["mensajes"])  # solo tras un acierto
    ok = enviar(client, h, did, SOLUCION)
    m = [m for m in ok["mensajes"] if m["tipo"] == "sobreconfianza"]
    assert len(m) == 1 and m[0]["clave"] == "sobreconfianza_acierto" and m[0]["texto"] == MENSAJES["sobreconfianza_acierto"]["texto"]
    assert any(e.detalle.endswith("tras un acierto") for e in eventos(db, "R11"))


def test_r11_sin_la_bandera_no_hay_mensaje(client, db):
    h, did = preparar(client, db)
    iniciar(client, h, did)
    ok = enviar(client, h, did, SOLUCION)
    assert all(m["tipo"] != "sobreconfianza" for m in ok["mensajes"]) and eventos(db, "R11") == []


def test_r11_la_bandera_llega_al_prompt_como_codigo(client, db, falso):
    h, did = preparar(client, db)
    poner_linea_base(db, banderas={**SOBRECONFIANZA, **DEPENDENCIA})
    iniciar(client, h, did)
    enviar(client, h, did)
    assert pedir_ayuda(client, h, did).status_code == 200
    p = falso.llamadas[0]
    assert "[BANDERA: sobreconfianza]" in p.prompt_sistema and "[BANDERA: dependencia]" in p.prompt_sistema
    assert "<banderas>dependencia, sobreconfianza</banderas>" in p.mensaje_usuario


def test_las_banderas_no_filtran_ns_indicadores_ni_datos_personales_al_prompt(client, db, falso):
    h, did = preparar(client, db)
    poner_linea_base(db, banderas={**SOBRECONFIANZA, **DEPENDENCIA})
    poner_ns(db, 2)
    iniciar(client, h, did)
    enviar(client, h, did), enviar(client, h, did)
    pedir_ayuda(client, h, did)
    p = falso.llamadas[0]
    junto = p.prompt_sistema + "\n" + p.mensaje_usuario
    for sigla in ("NS", "TA", "NI", "TR", "UA", "R9", "R11"):
        assert not re.search(rf"\b{sigla}\b", junto), sigla
    for palabra in ("indicador", "pct_", "riesgo", "senales", "ana@uni.edu", "Ana", "Pérez", "ns_maximo"):
        assert palabra not in junto, palabra
    assert p.tipo_ayuda == "AY2" and SOLUCION not in junto  # la solución solo viaja en AY3 y AY4


# ======================= R10: ensayo y error =======================
T0 = datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)


def _envios(*pasos):
    """pasos: (correcto, segundos desde el envío anterior)."""
    t, salida = T0, []
    for correcto, delta in pasos:
        t = t + timedelta(seconds=delta)
        salida.append((correcto, t))
    return salida


CASOS_R10 = [
    ("3 fallos con 10 s y 10 s", [(False, 0), (False, 10), (False, 10)], True),
    ("29.9 s todavía es menos de 30", [(False, 0), (False, 29.9), (False, 5)], True),
    ("30 s exactos no es menos de 30", [(False, 0), (False, 30), (False, 5)], False),
    ("una pausa larga entre el 2.º y el 3.º", [(False, 0), (False, 5), (False, 60)], False),
    ("solo 2 fallos", [(False, 0), (False, 5)], False),
    ("un acierto en medio", [(False, 0), (True, 5), (False, 5)], False),
    ("fallo, acierto, fallo, fallo", [(False, 0), (True, 5), (False, 5), (False, 5)], False),
    ("4 fallos rápidos: se miran los últimos 3", [(False, 0), (False, 100), (False, 5), (False, 5)], True),
]


@pytest.mark.parametrize("nombre,pasos,esperado", CASOS_R10, ids=[c[0] for c in CASOS_R10])
def test_r10_tabla_pura(nombre, pasos, esperado):
    assert es_ensayo_error(_envios(*pasos), REGLAS["r10_ensayo_error"]) is esperado


def test_r10_tres_fallos_rapidos_incluyen_la_reflexion_y_se_registra(client, db):
    h, did = preparar(client, db)
    iniciar(client, h, did)
    assert enviar(client, h, did)["reflexion"] is None
    assert enviar(client, h, did)["reflexion"] is None
    j = enviar(client, h, did)
    assert j["reflexion"] == {
        "clave": "ensayo_error", "tipo": "reflexion", "texto": MENSAJES["ensayo_error"]["texto"], "enlace": None, "ajuste_id": None,
    }
    ev = eventos(db, "R10")
    assert len(ev) == 1 and ev[0].indicadores["envio"] == 3 and ev[0].sesion_id == sesion_en_curso(db).id
    assert ev[0].concepto_id == concepto(db).id


def test_r10_no_se_repite_con_los_mismos_envios_y_vuelve_con_otros_tres(client, db):
    h, did = preparar(client, db)
    iniciar(client, h, did)
    salida = [enviar(client, h, did)["reflexion"] is not None for _ in range(6)]
    assert salida == [False, False, True, False, False, True]
    assert len(eventos(db, "R10")) == 2


def test_r10_con_30_s_o_mas_entre_envios_no_hay_reflexion(client, db):
    h, did = preparar(client, db)
    iniciar(client, h, did)
    enviar(client, h, did), enviar(client, h, did)
    ahora = ahora_utc()
    for i, n in enumerate((1, 2)):  # el 2.º y el 3.º quedan separados por más de 30 s
        db.execute(Intento.__table__.update().where(Intento.numero == n).values(creado_en=ahora - timedelta(seconds=120 - 40 * i)))
    db.commit()
    assert enviar(client, h, did)["reflexion"] is None and eventos(db, "R10") == []


def test_r10_no_bloquea_la_ayuda_ni_aparece_en_un_acierto(client, db, falso):
    h, did = preparar(client, db)
    iniciar(client, h, did)
    for _ in range(3):
        j = enviar(client, h, did)
    assert j["reflexion"] is not None
    assert pedir_ayuda(client, h, did).status_code == 200
    ok = enviar(client, h, did, SOLUCION)
    assert ok["reflexion"] is None and ok["desafio_resuelto"] is True


# ======================= Oferta de ayuda =======================
def _hasta_dos_fallos(client, db, prefs, ns=None):
    h, did = preparar(client, db)
    if prefs is not None:
        poner_linea_base(db, prefs=prefs)
    if ns is not None:
        poner_ns(db, ns)
    iniciar(client, h, did)
    return h, did


def test_oferta_tabla_pura_de_motivos():
    cfg = REGLAS["ayuda_en_desafio"]
    casos = [  # (ns, fallos, tr, motivo)
        (1, 0, 1.0, None), (1, 1, 1.49, None), (1, 2, 0.1, "fallos"), (1, 5, None, "fallos"), (1, 1, 1.5, "tiempo"),
        (1, 0, 2.0, "tiempo"), (0, 3, 3.0, None), (2, 2, 0.0, "fallos"), (3, 1, None, None),
    ]
    for ns, fallos, tr, esperado in casos:
        assert motivo_de_oferta(ns, fallos, tr, cfg) == esperado, (ns, fallos, tr)


@pytest.mark.parametrize("valor,esperado", [("a_solicitud", "a_solicitud"), ("ofrecer", "ofrecer"), ("mostrar_sola", "mostrar_sola"),
                                              ("otra_cosa", "ofrecer"), (None, "ofrecer")])
def test_preferencia_3_3_lee_el_codigo_y_usa_un_valor_por_defecto(client, db, valor, esperado):
    registrar(client)
    poner_linea_base(db, prefs={"3.3": valor} if valor else {})
    assert preferencia_ayuda(db, ana(db).id) == esperado


def test_preferencia_3_3_sin_diagnostico_ofrece(client, db):
    registrar(client)
    assert preferencia_ayuda(db, ana(db).id) == "ofrecer"


def test_oferta_a_solicitud_nunca_ofrece(client, db, falso):
    h, did = _hasta_dos_fallos(client, db, {"3.3": "a_solicitud"})
    assert enviar(client, h, did)["oferta_ayuda"] is None
    assert enviar(client, h, did)["oferta_ayuda"] is None and enviar(client, h, did)["oferta_ayuda"] is None


def test_oferta_ofrecer_aparece_con_dos_fallos_y_no_llama_al_llm(client, db, falso):
    h, did = _hasta_dos_fallos(client, db, {"3.3": "ofrecer"})
    assert enviar(client, h, did)["oferta_ayuda"] is None  # 1 fallo y TR bajo
    o = enviar(client, h, did)["oferta_ayuda"]
    assert (o["modo"], o["motivo"], o["tipo_ayuda"], o["ayuda"]) == ("ofrecer", "fallos", "AY1", None)
    assert o["texto"] == MENSAJES["oferta_ayuda"]["texto"] == "¿Quieres una pista?"
    assert o["boton"] and o["boton_rechazo"]
    assert falso.llamadas == [] and db.scalar(select(SolicitudAyuda)) is None  # solo se ofrece


def test_oferta_sin_preferencia_guardada_ofrece(client, db, falso):
    h, did = _hasta_dos_fallos(client, db, None)
    enviar(client, h, did)
    assert enviar(client, h, did)["oferta_ayuda"]["modo"] == "ofrecer"


def test_oferta_en_ns_0_no_existe_solo_el_boton(client, db, falso):
    h, did = _hasta_dos_fallos(client, db, {"3.3": "ofrecer"}, ns=0)
    for _ in range(4):
        assert enviar(client, h, did)["oferta_ayuda"] is None
    assert pedir_ayuda(client, h, did).json()["tipo_ayuda"] == "AY1"  # el botón sigue funcionando


def test_oferta_por_tiempo_con_un_solo_fallo(client, db, falso):
    h, did = _hasta_dos_fallos(client, db, {"3.3": "ofrecer"})
    s = sesion_en_curso(db)
    s.inicio = ahora_utc() - timedelta(seconds=200)  # TR = 200 / 120 = 1.67
    db.commit()
    o = enviar(client, h, did)["oferta_ayuda"]
    assert o["motivo"] == "tiempo" and o["modo"] == "ofrecer"


def test_oferta_mostrar_sola_pide_la_ayuda_y_la_marca(client, db, falso):
    h, did = _hasta_dos_fallos(client, db, {"3.3": "mostrar_sola"})
    assert enviar(client, h, did)["oferta_ayuda"] is None
    o = enviar(client, h, did)["oferta_ayuda"]
    assert o["modo"] == "mostrar_sola" and o["ayuda"]["tipo_ayuda"] == "AY1" and o["ayuda"]["mensaje"] == "Ayuda AY1"
    assert o["texto"] == MENSAJES["ayuda_mostrada_sola"]["texto"] and o["boton"] is None
    s = db.scalar(select(SolicitudAyuda))
    assert s.mostrada_sola is True and s.id == o["ayuda"]["solicitud_id"] and s.intentos_previos == 2
    assert sesion_en_curso(db).ayuda_mostrada_sola is True and len(falso.llamadas) == 1


def test_oferta_mostrar_sola_solo_muestra_la_primera_y_luego_ofrece(client, db, falso):
    h, did = _hasta_dos_fallos(client, db, {"3.3": "mostrar_sola"})
    enviar(client, h, did), enviar(client, h, did)
    o = enviar(client, h, did)["oferta_ayuda"]  # fallo nuevo tras la ayuda: ahora solo se ofrece la siguiente
    assert (o["modo"], o["tipo_ayuda"], o["ayuda"]) == ("ofrecer", "AY2", None)
    assert len(falso.llamadas) == 1


def test_oferta_no_se_repite_sin_un_fallo_nuevo_tras_una_ayuda(client, db, falso):
    h, did = _hasta_dos_fallos(client, db, {"3.3": "ofrecer"})
    enviar(client, h, did), enviar(client, h, did)
    assert pedir_ayuda(client, h, did).status_code == 200
    assert enviar(client, h, did)["oferta_ayuda"]["tipo_ayuda"] == "AY2"  # con un fallo nuevo vuelve a ofrecer


def test_oferta_nunca_ofrece_ay4_ni_en_una_verificacion(client, db, falso):
    h, did = _hasta_dos_fallos(client, db, {"3.3": "ofrecer"}, ns=3)
    for _ in range(3):
        enviar(client, h, did)
    pedir_ayuda(client, h, did)  # AY3 con 3 fallos
    o = enviar(client, h, did)["oferta_ayuda"]
    assert o is None or o["tipo_ayuda"] != "AY4"
    # verificación pendiente (R7): sin ayuda automática
    db.add(Verificacion(usuario_id=ana(db).id, concepto_id=concepto(db).id, desafio_id=did, origen="desafio", estado="pendiente"))
    db.commit()
    assert enviar(client, h, did)["oferta_ayuda"] is None


def test_oferta_mostrada_sola_no_hace_sa_ni_cuenta_para_ua(client, db, falso):
    h, did = _hasta_dos_fallos(client, db, {"3.3": "mostrar_sola"})
    enviar(client, h, did), enviar(client, h, did)
    ok = enviar(client, h, did, SOLUCION)
    assert ok["resultado_cierre"] != "SA"
    df = cierres_del_concepto(db, ana(db).id, concepto(db).id)
    assert bool(df["uso_ayuda"].iloc[0]) is False


def test_oferta_tras_un_acierto_no_hay_oferta(client, db, falso):
    h, did = _hasta_dos_fallos(client, db, {"3.3": "ofrecer"})
    enviar(client, h, did), enviar(client, h, did)
    ok = enviar(client, h, did, SOLUCION)
    assert ok["oferta_ayuda"] is None and ok["desafio_resuelto"] is True


def test_oferta_si_el_llm_falla_se_degrada_sin_error(client, db):
    from app.main import app
    from app.modules.asistencia.router import get_proveedor

    roto = Falso(excepcion=RuntimeError("sin red"))
    app.dependency_overrides[get_proveedor] = lambda: roto
    try:
        h, did = _hasta_dos_fallos(client, db, {"3.3": "mostrar_sola"})
        enviar(client, h, did)
        o = enviar(client, h, did)["oferta_ayuda"]  # la ayuda de respaldo se entrega sola; nunca un 500
        assert o["modo"] == "mostrar_sola" and o["ayuda"]["fue_respaldo"] is True
    finally:
        app.dependency_overrides.pop(get_proveedor, None)
