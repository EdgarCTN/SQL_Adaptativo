import copy

import pytest

from app.core.reglas import cargar_reglas
from app.modules.motor_retiro.contexto import ContextoRegla
from app.modules.motor_retiro.evaluador import REGLAS_DISPONIBLES, evaluar, ordenar_reglas
from app.modules.motor_retiro.indicadores import CierreReciente, calcular_indicadores
from app.modules.motor_retiro.reglas.base import Regla, ResultadoRegla


def c(res, intentos=1, t=30, ref=120):
    return CierreReciente(res, intentos, t, ref)


def ctx(ns, cierres, desde=None, config=None, **omision):
    return ContextoRegla(
        usuario_id=1, concepto_id=1, concepto_nombre="JOIN", ns_actual=ns, sesion_id=1,
        resultado_sesion=cierres[-1].resultado if cierres else None, cierres_recientes=cierres,
        desafios_desde_cambio=len(cierres) if desde is None else desde, config=config or cargar_reglas(), **omision,
    )


SA3 = [c("SA"), c("SA"), c("SA")]
SA3_2INT = [c("SA", 2), c("SA", 2), c("SA", 2)]  # éxito sin ayuda pero con 2 envíos: no es «limpio», R2 no corresponde

# (nombre, ns, cierres, desde_cambio, regla esperada, ns esperado)
CASOS = [
    # ----- R1 retiro estándar (los 3 SA con 1 intento y TR ≤ 1.0 ya son de R2: aquí R1 usa 2 intentos) -----
    ("R1 baja de 2 a 1", 2, SA3_2INT, None, "R1", 1),
    ("R1 baja de 1 a 0", 1, SA3_2INT, None, "R1", 0),
    ("R1 no aplica con NS0", 0, SA3, None, "R4", 0),
    ("R1 CP cuenta como éxito", 2, [c("CP")] * 3, None, "R1", 1),
    ("R1 límite TA=0.80 exacto", 2, [c("SA")] * 4 + [c("CE")], None, "R1", 1),
    ("R1 TA 0.75 no alcanza", 2, [c("SA")] * 3 + [c("CE")], None, "R4", 2),
    ("R1 límite TR=1.25 exacto", 2, [c("SA", 1, 150)] * 3, None, "R1", 1),
    ("R1 TR 1.26 no alcanza", 2, [c("SA", 1, 151)] * 3, None, "R4", 2),
    ("R1 límite NI=2 exacto", 2, [c("SA", 2), c("SA", 2), c("SA", 3)], None, "R1", 1),
    ("R1 NI=3 no alcanza", 2, [c("SA", 3), c("SA", 3), c("SA", 1)], None, "R4", 2),
    ("R1 sin tiempo medido no retira", 2, [c("SA", 1, None)] * 3, None, "R4", 2),
    ("R1 con 2 desafíos: datos insuficientes", 2, [c("SA"), c("SA")], None, "R4", 2),
    ("R1 exige ≥3 desafíos desde el cambio aunque la ventana tenga más", 2, SA3, 2, "R4", 2),
    ("R1 ventana de 5 con 8 desde el cambio", 2, [c("SA", 2)] * 5, 8, "R1", 1),
    # ----- R5 refuerzo -----
    ("R5 sube de 1 a 2", 1, [c("NR")] * 3, None, "R5", 2),
    ("R5 sube de 0 a 1", 0, [c("NR"), c("CE"), c("NR")], None, "R5", 1),
    ("R5 sube de 2 a 3", 2, [c("CE")] * 3, None, "R5", 3),
    ("R5 con NS3 corresponde pero se queda en 3", 3, [c("NR")] * 3, None, "R5", 3),
    ("R5 TA=0.50 exacto no refuerza", 1, [c("SA"), c("SA"), c("CE"), c("CE")], None, "R4", 1),
    ("R5 TA=0.40 de 5", 1, [c("SA"), c("SA")] + [c("NR")] * 3, None, "R5", 2),
    ("R5 NI≥4 con TA<0.80", 1, [c("SA", 4), c("CP", 4), c("CE", 4)], None, "R5", 2),
    ("R5 NI≥4 con TA=0.80 no refuerza", 1, [c("SA", 4)] * 4 + [c("CE", 4)], None, "R4", 1),
    ("R5 NI=3 con TA<0.80 no refuerza", 1, [c("SA", 3), c("CP", 3), c("CE", 3)], None, "R4", 1),
    ("R5 con 2 desafíos: datos insuficientes", 1, [c("NR"), c("NR")], None, "R4", 1),
    # ----- R4 mantener -----
    ("R4 sin cierres", 1, [], 0, "R4", 1),
    ("R4 TA intermedia", 2, [c("SA"), c("CE"), c("SA"), c("CE"), c("SA")], None, "R4", 2),
    ("R4 TA alta con muchos intentos", 2, [c("SA", 4)] * 3, None, "R4", 2),
    ("R4 TA alta con tiempo alto", 2, [c("SA", 1, 600)] * 3, None, "R4", 2),
]


@pytest.mark.parametrize("nombre,ns,cierres,desde,regla,ns_esperado", CASOS, ids=[x[0] for x in CASOS])
def test_tabla_de_casos(nombre, ns, cierres, desde, regla, ns_esperado):
    ev = evaluar(ctx(ns, cierres, desde))
    assert (ev.regla, ev.ns_nuevo) == (regla, ns_esperado), ev.motivo


def test_motivos_legibles():
    assert "datos insuficientes" in evaluar(ctx(1, [c("SA")])).motivo
    assert evaluar(ctx(2, SA3_2INT)).motivo.startswith("R1")
    assert evaluar(ctx(2, SA3)).motivo.startswith("R2")
    assert "máximo" in evaluar(ctx(3, [c("NR")] * 3)).motivo
    assert evaluar(ctx(2, SA3)).clave_mensaje == "retiro_automatico"  # R2 usa el mismo mensaje fijo que R1
    assert evaluar(ctx(2, SA3_2INT)).clave_mensaje == "retiro_automatico"
    assert evaluar(ctx(1, [c("NR")] * 3)).clave_mensaje == "refuerzo"
    assert evaluar(ctx(1, [])).clave_mensaje is None


def test_los_umbrales_salen_de_reglas_json():
    cfg = copy.deepcopy(cargar_reglas())
    cfg["retiro_refuerzo"]["ta_retiro_min"] = 1.0
    assert evaluar(ctx(2, [c("SA")] * 4 + [c("CE")], config=cfg)).regla == "R4"
    cfg = copy.deepcopy(cargar_reglas())
    cfg["ventana"]["minimo_desafios_desde_cambio"] = 2
    assert evaluar(ctx(2, [c("SA"), c("SA")], config=cfg)).regla == "R1"
    cfg["retiro_refuerzo"]["tr_retiro_estandar_max"] = 0.1
    assert evaluar(ctx(2, [c("SA", 1, 60)] * 2, config=cfg)).regla == "R4"


# ---------- Evaluador ----------
class Falsa(Regla):
    def __init__(self, codigo, aplica=True, ns=None):
        self.codigo, self._aplica, self._ns = codigo, aplica, ns

    def aplica(self, contexto):
        return self._aplica

    def ejecutar(self, contexto):
        return ResultadoRegla(self._ns if self._ns is not None else contexto.ns_actual, f"fake {self.codigo}")


def test_orden_segun_reglas_json_y_la_primera_detiene_a_las_demas():
    assert [r.codigo for r in ordenar_reglas(cargar_reglas()["orden_evaluacion_cierre"])] == [
        "R6", "R8", "R7", "R5", "R2", "R1", "R4",
    ]
    disp = {"R5": Falsa("R5", ns=2), "R1": Falsa("R1", ns=0), "R4": Falsa("R4")}
    assert evaluar(ctx(1, SA3), disp).regla == "R5"  # R5 antes que R1 aunque ambas correspondan
    cfg = copy.deepcopy(cargar_reglas())
    cfg["orden_evaluacion_cierre"] = ["R1", "R5", "R4"]
    assert evaluar(ctx(1, SA3, config=cfg), disp).regla == "R1"
    disp["R5"], disp["R1"] = Falsa("R5", aplica=False), Falsa("R1", aplica=False)
    assert evaluar(ctx(1, SA3), disp).regla == "R4"


def test_r4_siempre_cierra_la_secuencia_y_el_ns_se_acota():
    cfg = copy.deepcopy(cargar_reglas())
    cfg["orden_evaluacion_cierre"] = ["R5", "R1"]
    assert [r.codigo for r in ordenar_reglas(cfg["orden_evaluacion_cierre"])][-1] == "R4"
    assert evaluar(ctx(1, SA3), {"R4": Falsa("R4", ns=9)}).ns_nuevo == 3
    assert evaluar(ctx(1, SA3), {"R4": Falsa("R4", ns=-4)}).ns_nuevo == 0
    assert set(REGLAS_DISPONIBLES) == {"R6", "R8", "R7", "R5", "R2", "R1", "R4"}


# ---------- Indicadores ----------
def test_indicadores():
    ind = calcular_indicadores([c("SA", 1, 60), c("CP", 2, 120), c("CE", 5, 300), c("NR", 3, 120), c("SA", 1, 120)])
    assert ind.n == 5 and ind.ta == 0.6 and ind.ni == 2.0 and ind.tr == 1.0
    assert calcular_indicadores([]).ta is None
    assert calcular_indicadores([c("SA", 1, None)]).tr is None
    assert calcular_indicadores([c("NR", 0, 30)]).ni == 0.0  # abandonado sin envíos
    assert calcular_indicadores([c("SA", 1, 60), c("SA", 2, 120)]).ni == 1.5  # mediana de dos


# ---------- R8 y R7 (entrega 4): tabla de casos ----------
def _om(motivo, **kw):
    return {"omision_motivo": motivo, **kw}


# (nombre, ns, cierres, kwargs de omisión, regla, ns esperado, acción, extra)
CASOS_OMISION = [
    ("R8 NS0 sube a 1", 0, [], _om("muy_dificil", omisiones_muy_dificil_seguidas=1), "R8", 1, "sugerir", {}),
    ("R8 NS1 sube a 2", 1, [], _om("muy_dificil", omisiones_muy_dificil_seguidas=1), "R8", 2, "sugerir", {}),
    ("R8 NS2 sube a 3", 2, [], _om("muy_dificil", omisiones_muy_dificil_seguidas=1), "R8", 3, "sugerir", {}),
    ("R8 NS3 se queda en 3 (una sola omisión)", 3, [], _om("muy_dificil", omisiones_muy_dificil_seguidas=1), "R8", 3, "sugerir", {}),
    ("2 seguidas con NS3: R6 (b) va antes que R8 y la detiene", 3, [], _om("muy_dificil", omisiones_muy_dificil_seguidas=2), "R6", 3,
     "estancamiento", {"r6_condicion": "b", "prerrequisito": None, "prerrequisito_ns": None}),
    ("R8 NS2 y 2 seguidas: el NS no era 3, no se registra", 2, [], _om("muy_dificil", omisiones_muy_dificil_seguidas=2), "R8", 3, "sugerir", {}),
    ("R8 no mira la ventana (ni R5 ni R1)", 1, [c("NR")] * 5, _om("muy_dificil", omisiones_muy_dificil_seguidas=1), "R8", 2, "sugerir", {}),
    ("R7 con 1 omisión acumulada: solo se mantiene", 1, [], _om("muy_facil", omisiones_muy_facil=1), "R4", 1, "mantener", {}),
    ("R7 con 2: verificación y el NS no cambia", 2, [], _om("muy_facil", omisiones_muy_facil=2), "R7", 2, "verificacion", {}),
    ("R7 con 3: verificación", 0, [], _om("muy_facil", omisiones_muy_facil=3), "R7", 0, "verificacion", {}),
    ("R7 con una verificación pendiente no asigna otra", 1, [], _om("muy_facil", omisiones_muy_facil=2, verificacion_pendiente=True),
     "R4", 1, "mantener", {}),
    ("R7 no retira aunque la ventana sea perfecta (R1 no se evalúa)", 2, SA3 + [c("SA"), c("SA")], _om("muy_facil", omisiones_muy_facil=1),
     "R4", 2, "mantener", {}),
    ("Sin omisión R8 y R7 no intervienen: gana R5", 1, [c("NR")] * 3, {}, "R5", 2, "cambiar_ns", {}),
]


@pytest.mark.parametrize("nombre,ns,cierres,omision,regla,ns_esperado,accion,extra", CASOS_OMISION, ids=[x[0] for x in CASOS_OMISION])
def test_tabla_r8_y_r7(nombre, ns, cierres, omision, regla, ns_esperado, accion, extra):
    ev = evaluar(ctx(ns, cierres, **omision))
    assert (ev.regla, ev.ns_nuevo, ev.accion, ev.extra) == (regla, ns_esperado, accion, extra), nombre


def test_el_umbral_de_r7_sale_de_reglas_json():
    cfg = copy.deepcopy(cargar_reglas())
    cfg["r7_muy_facil"]["omisiones_para_verificacion"] = 3
    assert evaluar(ctx(1, [], config=cfg, **_om("muy_facil", omisiones_muy_facil=2))).regla == "R4"
    assert evaluar(ctx(1, [], config=cfg, **_om("muy_facil", omisiones_muy_facil=3))).regla == "R7"


def test_el_umbral_de_omisiones_seguidas_sale_de_reglas_json():
    cfg = copy.deepcopy(cargar_reglas())
    cfg["r6_estancamiento"]["omisiones_muy_dificil_seguidas"] = 3
    assert evaluar(ctx(3, [], config=cfg, **_om("muy_dificil", omisiones_muy_dificil_seguidas=2))).regla == "R8"
    assert evaluar(ctx(3, [], config=cfg, **_om("muy_dificil", omisiones_muy_dificil_seguidas=3))).regla == "R6"


def test_r8_conserva_su_marca_para_r6_solo_si_r6_no_esta_en_el_orden():
    """Sin R6 en orden_evaluacion_cierre (config recortada) R8 se comporta como en la entrega 4."""
    cfg = copy.deepcopy(cargar_reglas())
    cfg["orden_evaluacion_cierre"] = ["R8", "R7", "R5", "R2", "R1", "R4"]
    ev = evaluar(ctx(3, [], config=cfg, **_om("muy_dificil", omisiones_muy_dificil_seguidas=2)), {k: v for k, v in REGLAS_DISPONIBLES.items() if k != "R6"})
    assert (ev.regla, ev.extra) == ("R8", {"r6_b_pendiente": True})


# ---------- R2 y R6 (entrega 5): tablas de casos ----------
SA3_LENTOS = [c("SA", 1, 150)] * 3  # TR = 1.25: R1 sí, R2 no (acelerado exige TR ≤ 1.0)

# (nombre, ns, cierres, desde_cambio, regla esperada, ns esperado)
CASOS_R2 = [
    ("R2 baja 2 desde NS3", 3, SA3, None, "R2", 1),
    ("R2 baja 2 desde NS2", 2, SA3, None, "R2", 0),
    ("R2 desde NS1 llega al mínimo 0 (baja solo 1)", 1, SA3, None, "R2", 0),
    ("R2 no aplica con NS0", 0, SA3, None, "R4", 0),
    ("R2 límite TR=1.0 exacto", 2, [c("SA", 1, 120)] * 3, None, "R2", 0),
    ("R2 TR=1.01 ya no es acelerado: retira R1", 2, [c("SA", 1, 121)] * 3, None, "R1", 1),
    ("R2 TR=1.25: solo R1", 2, SA3_LENTOS, None, "R1", 1),
    ("R2 un envío extra en uno de los 3: retira R1, no R2", 2, [c("SA"), c("SA", 2), c("SA")], None, "R1", 1),
    ("R2 un CP entre los 3 no es SA: retira R1", 2, [c("SA"), c("CP"), c("SA")], None, "R1", 1),
    ("R2 un CE entre los 3: TA 0.67, no retira", 2, [c("SA"), c("CE"), c("SA")], None, "R4", 2),
    ("R2 una ayuda (aunque sea mostrada sola) deja el desafío en CP/CE, no SA", 2, [c("SA"), c("SA"), c("CP")], None, "R1", 1),
    ("R2 mira los 3 últimos aunque antes hubiera un CE en la ventana", 2, [c("CE", 1)] + SA3, None, "R2", 0),
    ("R2 el último cierre no limpio lo impide", 2, SA3 + [c("CE")], None, "R4", 2),
    ("R2 con 2 desafíos desde el cambio: datos insuficientes", 2, [c("SA"), c("SA")], None, "R4", 2),
    ("R2 exige 3 desafíos desde el cambio aunque la lista tenga 3", 2, SA3, 2, "R4", 2),
    ("R2 sin tiempo medido no retira", 2, [c("SA", 1, None)] * 3, None, "R4", 2),
    ("R2 usa el TR de los 3 últimos y no el de la ventana (PROVISIONAL)", 2,
     [c("SA", 1, 600)] * 3 + [c("SA", 1, 30)] * 2, None, "R2", 0),
]


@pytest.mark.parametrize("nombre,ns,cierres,desde,regla,ns_esperado", CASOS_R2, ids=[x[0] for x in CASOS_R2])
def test_tabla_r2(nombre, ns, cierres, desde, regla, ns_esperado):
    ev = evaluar(ctx(ns, cierres, desde))
    assert (ev.regla, ev.ns_nuevo) == (regla, ns_esperado), ev.motivo


def test_r2_cambia_ns_y_usa_el_mensaje_de_retiro():
    ev = evaluar(ctx(3, SA3))
    assert (ev.accion, ev.clave_mensaje) == ("cambiar_ns", "retiro_automatico") and "R2" in ev.motivo and "TR=0.25" in ev.motivo


def test_los_umbrales_de_r2_salen_de_reglas_json():
    cfg = copy.deepcopy(cargar_reglas())
    cfg["retiro_refuerzo"]["tr_retiro_acelerado_max"] = 0.2
    assert evaluar(ctx(2, SA3, config=cfg)).regla == "R1"  # TR 0.25 ya no es acelerado
    cfg = copy.deepcopy(cargar_reglas())
    cfg["retiro_refuerzo"]["desafios_limpios_acelerado"] = 4
    assert evaluar(ctx(2, SA3, config=cfg)).regla == "R1"
    assert evaluar(ctx(2, SA3 + [c("SA")], config=cfg)).regla == "R2"
    cfg = copy.deepcopy(cargar_reglas())
    cfg["retiro_refuerzo"]["intentos_desafio_limpio"] = 2
    assert evaluar(ctx(2, SA3_2INT, config=cfg)).regla == "R2"


NR3 = [c("NR")] * 3
PREVIO_DOMINADO = {"prerrequisito_codigo": "filtrado", "prerrequisito_nombre": "Filtrado (WHERE)", "prerrequisito_ns": 1}
PREVIO_SIN_DOMINAR = {"prerrequisito_codigo": "group_by", "prerrequisito_nombre": "GROUP BY", "prerrequisito_ns": 2}

# (nombre, ns, cierres, desde_cambio, kwargs del contexto, regla, ns esperado, clave del mensaje, condición de R6)
CASOS_R6 = [
    # (a) TA < 0.50, ≥ 3 desafíos desde el cambio, refuerzo previo
    ("R6 (a) NS3, TA baja, con refuerzo previo, sin prerrequisito: derivar", 3, NR3, None, {"refuerzos_previos": 1},
     "R6", 3, "estancamiento_derivar", "a"),
    ("R6 (a) prerrequisito dominado (NS1): derivar", 3, NR3, None, {"refuerzos_previos": 1, **PREVIO_DOMINADO},
     "R6", 3, "estancamiento_derivar", "a"),
    ("R6 (a) prerrequisito con NS0: derivar", 3, NR3, None, {"refuerzos_previos": 2, **PREVIO_DOMINADO, "prerrequisito_ns": 0},
     "R6", 3, "estancamiento_derivar", "a"),
    ("R6 (a) prerrequisito sin dominar (NS2): practicar el previo", 3, NR3, None, {"refuerzos_previos": 1, **PREVIO_SIN_DOMINAR},
     "R6", 3, "estancamiento_previo_sin_dominar", "a"),
    ("R6 (a) prerrequisito sin dominar (NS3): practicar el previo", 3, NR3, None,
     {"refuerzos_previos": 1, **PREVIO_SIN_DOMINAR, "prerrequisito_ns": 3}, "R6", 3, "estancamiento_previo_sin_dominar", "a"),
    ("R6 (a) límite: TA=0.40 de 5 desafíos", 3, [c("SA"), c("SA")] + NR3, None, {"refuerzos_previos": 1},
     "R6", 3, "estancamiento_derivar", "a"),
    ("R6 (a) sin refuerzo previo no aplica: R5 corresponde y se queda en 3", 3, NR3, None, {"refuerzos_previos": 0},
     "R5", 3, "refuerzo", None),
    ("R6 (a) TA=0.50 exacto no aplica", 3, [c("SA"), c("SA"), c("CE"), c("CE")], None, {"refuerzos_previos": 1},
     "R4", 3, None, None),
    ("R6 (a) con 2 desafíos desde el cambio: datos insuficientes", 3, [c("NR"), c("NR")], None, {"refuerzos_previos": 1},
     "R4", 3, None, None),
    ("R6 (a) exige 3 desde el cambio aunque la ventana tenga 3", 3, NR3, 2, {"refuerzos_previos": 1}, "R4", 3, None, None),
    ("R6 (a) solo con NS3: en NS2 sube R5", 2, NR3, None, {"refuerzos_previos": 1}, "R5", 3, "refuerzo", None),
    ("R6 (a) buen desempeño con NS3 no es estancamiento: retira R2", 3, SA3, None, {"refuerzos_previos": 1}, "R2", 1, "retiro_automatico", None),
    # (b) 2 omisiones «Muy difícil» seguidas con el NS ya en 3
    ("R6 (b) NS3 y 2 seguidas, sin prerrequisito: derivar", 3, [], None, _om("muy_dificil", omisiones_muy_dificil_seguidas=2),
     "R6", 3, "estancamiento_derivar", "b"),
    ("R6 (b) prerrequisito sin dominar: practicar el previo", 3, [], None,
     {**_om("muy_dificil", omisiones_muy_dificil_seguidas=2), **PREVIO_SIN_DOMINAR}, "R6", 3, "estancamiento_previo_sin_dominar", "b"),
    ("R6 (b) no necesita refuerzo previo ni mira la ventana", 3, SA3, None,
     {**_om("muy_dificil", omisiones_muy_dificil_seguidas=3), "refuerzos_previos": 0}, "R6", 3, "estancamiento_derivar", "b"),
    ("R6 (b) con una sola omisión sigue R8", 3, [], None, _om("muy_dificil", omisiones_muy_dificil_seguidas=1), "R8", 3, "refuerzo", None),
    ("R6 (b) con NS2 sigue R8 (el NS no era 3 al llegar)", 2, [], None,
     _om("muy_dificil", omisiones_muy_dificil_seguidas=2), "R8", 3, "refuerzo", None),
    ("R6 no corresponde a una omisión «Muy fácil»", 3, NR3, None,
     {**_om("muy_facil", omisiones_muy_facil=1), "refuerzos_previos": 1}, "R4", 3, None, None),
]


@pytest.mark.parametrize(
    "nombre,ns,cierres,desde,extra,regla,ns_esperado,clave,condicion", CASOS_R6, ids=[x[0] for x in CASOS_R6]
)
def test_tabla_r6(nombre, ns, cierres, desde, extra, regla, ns_esperado, clave, condicion):
    ev = evaluar(ctx(ns, cierres, desde, **extra))
    assert (ev.regla, ev.ns_nuevo, ev.clave_mensaje) == (regla, ns_esperado, clave), ev.motivo
    if regla == "R6":
        assert ev.accion == "estancamiento" and ev.extra["r6_condicion"] == condicion


def test_r6_registra_el_prerrequisito_y_explica_el_motivo():
    ev = evaluar(ctx(3, NR3, refuerzos_previos=1, **PREVIO_SIN_DOMINAR))
    assert ev.extra == {"r6_condicion": "a", "prerrequisito": "group_by", "prerrequisito_ns": 2}
    assert "TA=0.00" in ev.motivo and "«GROUP BY» sin dominar (NS 2)" in ev.motivo
    ev = evaluar(ctx(3, NR3, refuerzos_previos=1, **PREVIO_DOMINADO))
    assert "dominado (NS 1)" in ev.motivo and ev.extra["prerrequisito_ns"] == 1


def test_los_umbrales_de_r6_salen_de_reglas_json():
    cfg = copy.deepcopy(cargar_reglas())
    cfg["r6_estancamiento"]["ns_maximo_prerrequisito_dominado"] = 2  # ahora NS2 cuenta como dominado
    assert evaluar(ctx(3, NR3, config=cfg, refuerzos_previos=1, **PREVIO_SIN_DOMINAR)).clave_mensaje == "estancamiento_derivar"
    cfg = copy.deepcopy(cargar_reglas())
    cfg["retiro_refuerzo"]["ta_refuerzo_max"] = 0.2  # TA 0.0 sigue siendo menor; TA 0.4 ya no
    assert evaluar(ctx(3, [c("SA"), c("SA")] + NR3, config=cfg, refuerzos_previos=1)).regla == "R4"
    cfg = copy.deepcopy(cargar_reglas())
    cfg["ventana"]["minimo_desafios_desde_cambio"] = 2
    assert evaluar(ctx(3, [c("NR"), c("NR")], config=cfg, refuerzos_previos=1)).regla == "R6"


def test_prioridad_r6_antes_que_r5_y_r5_antes_que_r2_r1():
    """R6 detiene a R5 con NS3 (TA baja y refuerzo previo); sin refuerzo previo manda R5. R2 va antes que R1."""
    assert evaluar(ctx(3, NR3, refuerzos_previos=1)).regla == "R6"
    assert evaluar(ctx(3, NR3, refuerzos_previos=0)).regla == "R5"
    disp = {"R6": Falsa("R6", aplica=False), "R5": Falsa("R5", aplica=False), "R2": Falsa("R2", ns=0), "R1": Falsa("R1", ns=2), "R4": Falsa("R4")}
    assert evaluar(ctx(3, SA3), disp).regla == "R2"
    disp["R2"] = Falsa("R2", aplica=False)
    assert evaluar(ctx(3, SA3), disp).regla == "R1"
    disp["R6"] = Falsa("R6", ns=3)
    assert evaluar(ctx(3, SA3), disp).regla == "R6"  # R6 antes que todas
