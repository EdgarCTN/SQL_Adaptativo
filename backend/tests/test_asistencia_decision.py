import copy

import pytest

from app.core.reglas import cargar_reglas
from app.modules.asistencia.cierre import clasificar_cierre
from app.modules.asistencia.decision import DecisionAyuda, decidir_ayuda, primera_ayuda

# (ns, fallos, ayudas_previas, fallos_desde_ultima, tipo, reformulada, degradada)
CASOS_DECISION = [
    # primera ayuda según NS (la solicitud siempre es del estudiante, también en NS0)
    (0, 0, [], 0, "AY1", False, False),
    (1, 0, [], 0, "AY1", False, False),
    (2, 0, [], 0, "AY2", False, False),
    (3, 2, [], 0, "AY3", False, False),
    # mínimo de fallos de AY3 = 2: si no se cumple, el tipo inmediatamente inferior
    (3, 0, [], 0, "AY2", False, True),
    (3, 1, [], 0, "AY2", False, True),
    # nueva solicitud: sube un tipo solo si hubo un fallo nuevo desde la última ayuda
    (1, 1, ["AY1"], 1, "AY2", False, False),
    (1, 0, ["AY1"], 0, "AY1", True, False),
    (2, 1, ["AY2"], 0, "AY2", True, False),
    (2, 2, ["AY2"], 1, "AY3", False, False),
    (2, 1, ["AY2"], 1, "AY2", True, True),  # AY3 sin los 2 fallos: baja a AY2 (que repite)
    (1, 3, ["AY1", "AY2", "AY3"], 1, "AY4", False, False),  # AY4 con 3 fallos
    (1, 2, ["AY1", "AY2", "AY3"], 1, "AY3", True, True),  # AY4 sin los 3 fallos: baja a AY3
    (1, 2, ["AY1", "AY2", "AY3"], 0, "AY3", True, False),
    # tras AY4 solo corresponde el recordatorio
    (1, 5, ["AY1", "AY4"], 2, None, False, False),
]


@pytest.mark.parametrize("ns,fallos,previas,desde,tipo,reform,degradada", CASOS_DECISION)
def test_tabla_de_decision(ns, fallos, previas, desde, tipo, reform, degradada):
    d = decidir_ayuda(ns, fallos, previas, desde)
    assert d.tipo == tipo and d.reformulada is reform and d.degradada is degradada
    assert d.ya_vio_ay4 is (tipo is None)


def test_ay4_nunca_es_la_primera_ayuda_aunque_la_configuracion_lo_diga():
    reglas = copy.deepcopy(cargar_reglas())
    reglas["primera_ayuda_por_ns"]["3"] = "AY4"
    d = decidir_ayuda(3, 10, [], 0, reglas)
    assert d.tipo == "AY3"


def test_ay4_solo_se_alcanza_desde_ay3_nunca_desde_cero():
    for ns in range(4):
        assert decidir_ayuda(ns, 99, [], 0).tipo != "AY4"


def test_los_minimos_salen_de_reglas_json():
    reglas = copy.deepcopy(cargar_reglas())
    reglas["ayuda_en_desafio"]["minimo_fallos_ay3"] = 5
    assert decidir_ayuda(3, 4, [], 0, reglas).tipo == "AY2"
    assert decidir_ayuda(3, 5, [], 0, reglas).tipo == "AY3"
    reglas["ayuda_en_desafio"]["minimo_fallos_ay4"] = 1
    assert decidir_ayuda(1, 1, ["AY3"], 1, reglas).tipo == "AY4"


def test_ns_fuera_de_rango_se_acota():
    assert primera_ayuda(-1) == "AY1" and primera_ayuda(9) == primera_ayuda(3)


def test_la_decision_es_inmutable():
    with pytest.raises(Exception):
        decidir_ayuda(1, 0, [], 0).tipo = "AY2"  # type: ignore[misc]
    assert isinstance(decidir_ayuda(1, 0, [], 0), DecisionAyuda)


# ---------- Cierre (Tabla 3) ----------
CASOS_CIERRE = [
    (0, [], "SA"), (1, [], "SA"), (2, [], "SA"), (3, [], "SA"),
    (0, ["AY1"], "CP"),  # en NS0, la AY1 pedida es la prevista
    (0, ["AY2"], "CE"),
    (1, ["AY1"], "CP"), (1, ["AY1", "AY1"], "CP"), (1, ["AY1", "AY2"], "CE"),
    (2, ["AY2"], "CP"), (2, ["AY1", "AY2"], "CP"), (2, ["AY3"], "CE"),
    (3, ["AY3"], "CP"), (3, ["AY2", "AY3"], "CP"),
    (1, ["AY4"], "NR"), (3, ["AY3", "AY4"], "NR"), (0, ["AY1", "AY2", "AY3", "AY4"], "NR"),
]


@pytest.mark.parametrize("ns,tipos,esperado", CASOS_CIERRE)
def test_clasificar_cierre(ns, tipos, esperado):
    assert clasificar_cierre(tipos, ns) == esperado
