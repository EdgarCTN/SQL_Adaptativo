import pytest
from sqlalchemy import delete, select

from app.modules.auth.models import Usuario
from app.modules.desafios import hooks
from app.modules.desafios.models import Concepto, Desafio, Intento, SesionDesafio
from conftest import API, cabecera, registrar, token_de

SETUP = """
CREATE TABLE libros (id INTEGER PRIMARY KEY, titulo TEXT, anio INTEGER);
INSERT INTO libros VALUES (1,'A',2001),(2,'B',1999),(3,'C',2015);
"""
SOLUCION = "SELECT titulo FROM libros WHERE anio > 2000"
PROHIBIDAS = ("solucion_referencia", "ayudas_respaldo", "sandbox_setup_sql", "errores_tipicos")


@pytest.fixture(autouse=True)
def _sin_desafios_sembrados(client, db):
    """Estas pruebas parten de cero: se quitan los 6 desafíos que siembra el sistema."""
    db.execute(delete(Desafio))
    db.commit()


def crear_desafio(db, codigo="filtrado", dificultad="D1", titulo="Libros recientes", activo=True) -> int:
    c = db.scalar(select(Concepto).where(Concepto.codigo == codigo))
    d = Desafio(
        titulo=titulo, enunciado="Lista los títulos publicados después de 2000.", recursos=["Cláusula WHERE"],
        concepto_id=c.id, dificultad=dificultad, esquema_sql="CREATE TABLE libros (...);",
        sandbox_setup_sql=SETUP, solucion_referencia=SOLUCION, errores_tipicos=["usar >= en vez de >"],
        ayudas_respaldo={"AY1": {"mensaje": "SECRETO_AYUDA", "codigo_sql": None}}, tiempo_referencia_seg=120, activo=activo,
    )
    db.add(d)
    db.commit()
    return d.id


def estudiante(client):
    registrar(client)
    return cabecera(token_de(client))


def test_listado_vacio_ex1(client):
    h = estudiante(client)
    r = client.get(f"{API}/desafios", headers=h)
    assert r.status_code == 200
    j = r.json()
    assert j["total"] == 0 and j["mensaje"] and [g["dificultad"] for g in j["grupos"]] == ["D1", "D2", "D3"]


def test_listado_agrupado_filtro_y_estado(client, db):
    h = estudiante(client)
    a = crear_desafio(db)
    crear_desafio(db, "join", "D2", "Prestamos")
    crear_desafio(db, "ordenamiento", "D1", "Oculto", activo=False)
    j = client.get(f"{API}/desafios", headers=h).json()
    assert j["total"] == 2 and j["mensaje"] is None
    assert [len(g["desafios"]) for g in j["grupos"]] == [1, 1, 0]
    assert {c["codigo"] for c in j["conceptos"]} == {"filtrado", "join"}
    j = client.get(f"{API}/desafios", params={"concepto": "join"}, headers=h).json()
    assert j["total"] == 1 and len(j["conceptos"]) == 2
    j = client.get(f"{API}/desafios", params={"concepto": "having"}, headers=h).json()
    assert j["total"] == 0 and "concepto" in j["mensaje"]
    client.post(f"{API}/desafios/{a}/iniciar", headers=h)
    d1 = client.get(f"{API}/desafios", headers=h).json()["grupos"][0]["desafios"][0]
    assert d1["estado"] == "en_curso"


def test_detalle_no_expone_datos_internos(client, db):
    h = estudiante(client)
    did = crear_desafio(db)
    r = client.get(f"{API}/desafios/{did}", headers=h)
    assert r.status_code == 200
    j = r.json()
    assert j["titulo"] == "Libros recientes" and j["esquema_sql"] and j["sesion_en_curso"] is None
    for clave in PROHIBIDAS:
        assert clave not in j
    for texto in (SOLUCION, "SECRETO_AYUDA", "INSERT INTO"):
        assert texto not in r.text


def test_desafio_inexistente_o_inactivo_ex2(client, db):
    h = estudiante(client)
    inactivo = crear_desafio(db, titulo="Apagado", activo=False)
    for did in (9999, inactivo):
        for metodo, ruta in (("get", ""), ("post", "/iniciar"), ("post", "/abandonar")):
            r = getattr(client, metodo)(f"{API}/desafios/{did}{ruta}", headers=h)
            assert r.status_code == 404 and r.json()["error"] is True and "no está disponible" in r.json()["mensaje"]
    r = client.post(f"{API}/desafios/9999/intentos", json={"codigo": "SELECT 1"}, headers=h)
    assert r.status_code == 404


def test_flujo_iniciar_fallar_acertar(client, db):
    h = estudiante(client)
    did = crear_desafio(db)
    r = client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    assert r.status_code == 200 and r.json()["reanudada"] is False
    sesion_id = r.json()["sesion_id"]
    r2 = client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    assert r2.json()["sesion_id"] == sesion_id and r2.json()["reanudada"] is True

    r = client.post(f"{API}/desafios/{did}/intentos", json={"codigo": "SELECT titulo FROM libros"}, headers=h)
    j = r.json()
    assert r.status_code == 200 and j["numero"] == 1 and j["correcto"] is False
    assert j["desafio_resuelto"] is False and j["estado_sesion"] == "en_curso" and j["filas"]
    r = client.post(f"{API}/desafios/{did}/intentos", json={"codigo": "SELECT titulo FROM libro"}, headers=h)
    j = r.json()
    assert j["numero"] == 2 and j["tipo_resultado"] == "error_sql" and "no such table" in j["detalle_tecnico"]
    r = client.post(f"{API}/desafios/{did}/intentos", json={"codigo": SOLUCION}, headers=h)
    j = r.json()
    assert j["numero"] == 3 and j["correcto"] and j["desafio_resuelto"]
    assert j["estado_sesion"] == "resuelto" and j["resultado_cierre"] == "SA"
    assert isinstance(j["tiempo_activo_seg"], int) and j["tiempo_activo_seg"] >= 0

    ses = db.scalar(select(SesionDesafio).where(SesionDesafio.id == sesion_id))
    assert ses.estado == "resuelto" and ses.resultado_cierre == "SA" and ses.fin is not None
    assert ses.tiempo_activo_seg == round((ses.fin - ses.inicio).total_seconds())
    numeros = list(db.scalars(select(Intento.numero).where(Intento.sesion_id == sesion_id).order_by(Intento.numero)))
    assert numeros == [1, 2, 3]
    # ya cerrada: no admite más envíos
    r = client.post(f"{API}/desafios/{did}/intentos", json={"codigo": SOLUCION}, headers=h)
    assert r.status_code == 409 and r.json()["error"] is True
    assert client.get(f"{API}/desafios/{did}", headers=h).json()["estado"] == "resuelto"


def test_intento_sin_sesion_y_validacion_ex3(client, db):
    h = estudiante(client)
    did = crear_desafio(db)
    r = client.post(f"{API}/desafios/{did}/intentos", json={"codigo": SOLUCION}, headers=h)
    assert r.status_code == 409 and "Inícialo" in r.json()["mensaje"]
    client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    for cuerpo in ({"codigo": ""}, {"codigo": "   \n "}, {"codigo": "x" * 4001}, {}):
        r = client.post(f"{API}/desafios/{did}/intentos", json=cuerpo, headers=h)
        assert r.status_code == 422 and r.json()["error"] is True
    assert "Escribe tu consulta" in client.post(
        f"{API}/desafios/{did}/intentos", json={"codigo": " "}, headers=h
    ).json()["mensaje"]
    assert db.scalar(select(Intento.id)) is None  # los inválidos no cuentan como intento
    r = client.post(f"{API}/desafios/{did}/intentos", json={"codigo": "x" * 4000}, headers=h)
    assert r.status_code == 200 and r.json()["correcto"] is False


def test_sentencia_peligrosa_es_un_intento_fallido_y_no_modifica_nada(client, db):
    h = estudiante(client)
    did = crear_desafio(db)
    client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    r = client.post(f"{API}/desafios/{did}/intentos", json={"codigo": "DROP TABLE libros"}, headers=h)
    assert r.status_code == 200 and r.json()["tipo_resultado"] == "no_permitida" and r.json()["correcto"] is False
    r = client.post(f"{API}/desafios/{did}/intentos", json={"codigo": SOLUCION}, headers=h)
    assert r.json()["correcto"] is True


def test_abandonar_cierra_como_nr(client, db):
    h = estudiante(client)
    did = crear_desafio(db)
    assert client.post(f"{API}/desafios/{did}/abandonar", headers=h).status_code == 409  # nada en curso
    sid = client.post(f"{API}/desafios/{did}/iniciar", headers=h).json()["sesion_id"]
    r = client.post(f"{API}/desafios/{did}/abandonar", headers=h)
    j = r.json()
    assert r.status_code == 200 and j["estado"] == "abandonado" and j["resultado_cierre"] == "NR"
    ses = db.scalar(select(SesionDesafio).where(SesionDesafio.id == sid))
    assert ses.estado == "abandonado" and ses.fin is not None and ses.tiempo_activo_seg is not None
    assert client.get(f"{API}/desafios/{did}", headers=h).json()["estado"] == "sin_iniciar"
    # se puede volver a empezar con una sesión nueva
    assert client.post(f"{API}/desafios/{did}/iniciar", headers=h).json()["sesion_id"] != sid


def test_hook_se_invoca_al_resolver_y_abandonar_y_su_fallo_no_rompe(client, db, monkeypatch):
    h = estudiante(client)
    a, b = crear_desafio(db), crear_desafio(db, "join", "D2", "Otro")
    llamadas = []
    monkeypatch.setattr(hooks, "al_cerrar_desafio", lambda _db, ses: llamadas.append(ses.resultado_cierre))
    client.post(f"{API}/desafios/{a}/iniciar", headers=h)
    client.post(f"{API}/desafios/{a}/intentos", json={"codigo": "SELECT titulo FROM libros"}, headers=h)
    assert llamadas == []  # un intento fallido no cierra
    client.post(f"{API}/desafios/{a}/intentos", json={"codigo": SOLUCION}, headers=h)
    client.post(f"{API}/desafios/{b}/iniciar", headers=h)
    client.post(f"{API}/desafios/{b}/abandonar", headers=h)
    assert llamadas == ["SA", "NR"]

    def falla(_db, _ses):
        raise RuntimeError("motor caído")

    monkeypatch.setattr(hooks, "al_cerrar_desafio", falla)
    client.post(f"{API}/desafios/{b}/iniciar", headers=h)
    r = client.post(f"{API}/desafios/{b}/abandonar", headers=h)
    assert r.status_code == 200 and r.json()["resultado_cierre"] == "NR"


def test_desafio_con_setup_roto_responde_controlado(client, db):
    h = estudiante(client)
    did = crear_desafio(db)
    d = db.get(Desafio, did)
    d.sandbox_setup_sql = "CREATE TABLE"
    db.commit()
    client.post(f"{API}/desafios/{did}/iniciar", headers=h)
    r = client.post(f"{API}/desafios/{did}/intentos", json={"codigo": "SELECT 1"}, headers=h)
    assert r.status_code == 503 and r.json()["error"] is True and "sqlite" not in r.text.lower()
    assert db.scalar(select(Intento.id)) is None


def test_sesiones_de_cada_estudiante_son_independientes(client, db):
    h1 = estudiante(client)
    registrar(client, "Luis", "luis@uni.edu", "Clave12345")
    h2 = cabecera(token_de(client, "luis@uni.edu"))
    did = crear_desafio(db)
    s1 = client.post(f"{API}/desafios/{did}/iniciar", headers=h1).json()["sesion_id"]
    s2 = client.post(f"{API}/desafios/{did}/iniciar", headers=h2).json()["sesion_id"]
    assert s1 != s2
    client.post(f"{API}/desafios/{did}/intentos", json={"codigo": SOLUCION}, headers=h1)
    assert client.get(f"{API}/desafios/{did}", headers=h2).json()["estado"] == "en_curso"


def test_requiere_sesion_y_rol_estudiante(client, db):
    did = crear_desafio(db)
    for metodo, ruta in (("get", ""), ("get", f"/{did}"), ("post", f"/{did}/iniciar"),
                         ("post", f"/{did}/intentos"), ("post", f"/{did}/abandonar")):
        assert getattr(client, metodo)(f"{API}/desafios{ruta}").status_code == 401
    registrar(client, "Doc", "doc@uni.edu", "Clave12345")
    u = db.scalar(select(Usuario).where(Usuario.correo == "doc@uni.edu"))
    u.rol = "docente"
    db.commit()
    h = cabecera(token_de(client, "doc@uni.edu"))
    assert client.get(f"{API}/desafios", headers=h).status_code == 403
