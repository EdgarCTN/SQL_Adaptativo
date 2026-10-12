import pytest

from app.modules.desafios.sandbox import (
    ErrorConfiguracionDesafio,
    evaluar_consulta,
    primera_palabra,
    tiene_order_by_superior,
)

SETUP = """
CREATE TABLE libros (id INTEGER PRIMARY KEY, titulo TEXT, anio INTEGER, precio REAL);
INSERT INTO libros VALUES (1,'A',2001,10.5),(2,'B',1999,20.0),(3,'C',2015,5.25),(4,'D',2020,7.0);
"""
SOL = "SELECT titulo FROM libros WHERE anio > 2000"


def ev(consulta, solucion=SOL, **kw):
    return evaluar_consulta(SETUP, solucion, consulta, **kw)


def test_solucion_correcta_ignora_orden_y_nombres_de_columna():
    assert ev(SOL).correcto
    r = ev("SELECT titulo AS nombre FROM libros WHERE anio >= 2001 ORDER BY precio DESC")
    assert r.correcto and r.tipo == "correcto"


def test_respeta_el_orden_si_la_solucion_tiene_order_by():
    sol = "SELECT titulo FROM libros ORDER BY anio"
    assert ev(sol, sol).correcto
    r = ev("SELECT titulo FROM libros ORDER BY anio DESC", sol)
    assert not r.correcto and "orden" in r.mensaje


def test_order_by_dentro_de_ventana_no_cuenta_como_orden_superior():
    assert not tiene_order_by_superior("SELECT ROW_NUMBER() OVER (ORDER BY anio) FROM libros")
    assert tiene_order_by_superior("SELECT titulo FROM libros ORDER BY anio")
    assert not tiene_order_by_superior("SELECT 'order by' AS t -- order by\n FROM libros")


@pytest.mark.parametrize(
    "consulta,esperado",
    [
        ("SELECT titulo FROM libros", "filas"),
        ("SELECT titulo, anio FROM libros WHERE anio > 2000", "columnas"),
        ("SELECT titulo FROM libros WHERE anio > 2001", "filas"),
        ("SELECT titulo FROM libros WHERE anio <> 2001", "coinciden"),
    ],
)
def test_resultado_distinto(consulta, esperado):
    r = ev(consulta)
    assert not r.correcto and r.tipo == "resultado_distinto" and esperado in r.mensaje


@pytest.mark.parametrize(
    "consulta",
    [
        "DROP TABLE libros",
        "INSERT INTO libros VALUES (9,'Z',2000,1)",
        "UPDATE libros SET precio = 0",
        "DELETE FROM libros",
        "ATTACH DATABASE ':memory:' AS otra",
        "PRAGMA table_info(libros)",
        "CREATE TABLE x (a INT)",
        "EXPLAIN SELECT 1",
        "WITH x AS (SELECT 1) DELETE FROM libros",
        "SELECT * FROM sqlite_master",
        "SELECT * FROM pragma_table_info('libros')",
        "SELECT load_extension('x')",
    ],
)
def test_sandbox_rechaza_operaciones_no_permitidas(consulta):
    r = ev(consulta)
    assert not r.correcto and r.tipo == "no_permitida"
    assert "no está permitida" in r.mensaje


def test_rechaza_varias_sentencias():
    for c in ("SELECT 1; SELECT 2", "SELECT titulo FROM libros; DROP TABLE libros"):
        r = ev(c)
        assert not r.correcto and r.tipo == "varias_sentencias"
    assert ev(SOL + ";  -- fin").correcto  # un solo punto y coma final sí vale


def test_la_base_no_cambia_entre_envios():
    ev("DELETE FROM libros")
    assert ev(SOL).correcto


def test_tiempo_limite():
    lento = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT count(*) FROM c"
    r = ev(lento, tiempo_max_seg=0.3)
    assert not r.correcto and r.tipo == "tiempo_agotado" and "tardó demasiado" in r.mensaje


def test_tope_de_filas_y_celdas_largas():
    r = ev("WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c LIMIT 50) SELECT x FROM c", max_filas=10)
    assert r.truncado and len(r.filas) == 10 and not r.correcto
    r = ev("SELECT replace(hex(zeroblob(5000)), '0', 'ab')")
    assert len(r.filas[0][0]) <= 201


def test_errores_en_lenguaje_claro_con_detalle_tecnico():
    r = ev("SELECT titulo FROM libro")
    assert r.tipo == "error_sql" and "«libro»" in r.mensaje and "no such table" in r.detalle_tecnico
    r = ev("SELECT autor FROM libros")
    assert "«autor»" in r.mensaje
    r = ev("SELEC titulo FROM libros")
    assert r.tipo == "no_permitida"
    r = ev("SELECT titulo FROM libros WHERE")
    assert r.tipo == "error_sql" and r.detalle_tecnico
    assert ev("   ").tipo == "vacia"


def test_primera_palabra_ignora_comentarios():
    assert primera_palabra("-- hola\n  /* x */ select 1") == "select"
    assert primera_palabra("(SELECT 1)") == "select"


def test_setup_o_solucion_invalidos_lanzan_error_de_configuracion():
    with pytest.raises(ErrorConfiguracionDesafio):
        evaluar_consulta("CREATE TABLE", SOL, SOL)
    with pytest.raises(ErrorConfiguracionDesafio):
        evaluar_consulta(SETUP, "SELECT x FROM nada", SOL)
