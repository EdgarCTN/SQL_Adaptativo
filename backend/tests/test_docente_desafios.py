"""Entrega 12: rol docente y banco de desafíos con validación automática."""
import copy

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.core.seguridad import hashear_password
from app.modules.auth.models import Rol, Usuario
from app.modules.desafios.models import Desafio, Intento, SesionDesafio
from app.modules.desafios.seeds import DESAFIOS
from app.modules.docente.validacion import validar_contenido
from app.seeds.seed import sembrar_docente
from conftest import API, cabecera, registrar, token_de

RUTA = f"{API}/docente/desafios"
BASE = DESAFIOS[0]  # novelas recientes (filtrado, D1): se sabe que es válido


def _datos_seed(d: dict) -> dict:
    return {
        "titulo": d["titulo"], "enunciado": d["enunciado"], "dificultad": d["dificultad"],
        "esquema_sql": d["esquema"], "sandbox_setup_sql": d["esquema"] + "\n" + d["datos"].strip(),
        "solucion_referencia": d["solucion"],
        "errores_tipicos": [{"descripcion": a, "ejemplo": b} for a, b in d["errores"]],
        "ayudas_respaldo": d["ayudas"],
    }


def payload(titulo="Novelas del club de lectura", **cambios) -> dict:
    """Payload válido de la API (copia del primer desafío sembrado con otro título)."""
    p = {
        "titulo": titulo, "enunciado": BASE["enunciado"], "recursos": list(BASE["recursos"]), "concepto": BASE["concepto"],
        "dificultad": BASE["dificultad"], "esquema_sql": BASE["esquema"],
        "sandbox_setup_sql": BASE["esquema"] + "\n" + BASE["datos"].strip(), "solucion_referencia": BASE["solucion"],
        "errores_tipicos": [{"descripcion": a, "ejemplo": b} for a, b in BASE["errores"]],
        "ayudas_respaldo": copy.deepcopy(BASE["ayudas"]),
    }
    p.update(cambios)
    return p


def _usuario(db, rol: Rol, correo: str) -> None:
    db.add(Usuario(nombre=rol.value.title(), correo=correo, rol=rol.value, hash_password=hashear_password("Clave12345")))
    db.commit()


@pytest.fixture
def docente(client, db):
    _usuario(db, Rol.docente, "profe@uni.edu")
    return cabecera(token_de(client, "profe@uni.edu", "Clave12345"))


@pytest.fixture
def estudiante(client):
    registrar(client)
    return cabecera(token_de(client))


# ---------- Permisos ----------
def test_estudiante_recibe_403_en_todas_las_rutas_docentes(client, estudiante):
    llamadas = [
        ("get", ""), ("get", "/opciones"), ("get", "/1"), ("post", ""), ("post", "/validar"), ("put", "/1"),
        ("post", "/1/activar"), ("post", "/1/desactivar"), ("delete", "/1"),
    ]
    for metodo, sufijo in llamadas:
        kw = {"json": payload()} if metodo in ("post", "put") else {}
        r = client.request(metodo.upper(), RUTA + sufijo, headers=estudiante, **kw)
        assert r.status_code == 403, f"{metodo} {sufijo} dio {r.status_code}"
        assert r.json()["error"] is True and "permiso" in r.json()["mensaje"]


def test_sin_sesion_401(client):
    assert client.get(RUTA).status_code == 401


def test_docente_y_administrador_acceden(client, db, docente):
    assert client.get(RUTA, headers=docente).status_code == 200
    _usuario(db, Rol.administrador, "admin@uni.edu")
    h = cabecera(token_de(client, "admin@uni.edu", "Clave12345"))
    assert client.get(RUTA, headers=h).status_code == 200
    assert client.get(f"{RUTA}/opciones", headers=h).json()["dificultades"] == ["D1", "D2", "D3"]


def test_estudiante_sigue_usando_sus_rutas(client, estudiante):
    assert client.get(f"{API}/desafios", headers=estudiante).status_code == 200


# ---------- Seed del docente ----------
def test_seed_docente_opcional(client, db, monkeypatch):
    sembrar_docente(db)  # vacíos: no se crea
    assert db.scalar(select(func.count()).select_from(Usuario).where(Usuario.rol == "docente")) == 0
    monkeypatch.setattr(settings, "docente_email", " Profe.Seed@Uni.edu ")
    monkeypatch.setattr(settings, "docente_password", "Docente12345!")
    sembrar_docente(db)
    sembrar_docente(db)  # idempotente
    u = db.scalar(select(Usuario).where(Usuario.correo == "profe.seed@uni.edu"))
    assert u is not None and u.rol == "docente"
    assert client.post(f"{API}/auth/login", json={"correo": "profe.seed@uni.edu", "contrasena": "Docente12345!"}).status_code == 200


def test_seed_docente_no_modifica_un_correo_existente(client, db, monkeypatch):
    registrar(client, correo="ana@uni.edu")
    monkeypatch.setattr(settings, "docente_email", "ana@uni.edu")
    monkeypatch.setattr(settings, "docente_password", "OtraClave123!")
    sembrar_docente(db)
    assert db.scalar(select(Usuario.rol).where(Usuario.correo == "ana@uni.edu")) == "estudiante"


# ---------- Validación ----------
def test_los_16_desafios_sembrados_son_validos():
    for d in DESAFIOS:
        assert validar_contenido({**_datos_seed(d), "recursos": []}) == [], d["titulo"]


def _campos(client, h, **cambios) -> dict[str, str]:
    r = client.post(f"{RUTA}/validar", json=payload(**cambios), headers=h)
    assert r.status_code == 200
    return {p["campo"]: p["mensaje"] for p in r.json()["problemas"]}


def test_payload_valido_pasa(client, docente):
    r = client.post(f"{RUTA}/validar", json=payload(), headers=docente)
    assert r.json() == {"valido": True, "problemas": []}


def _con_ayuda(tipo: str, **campos) -> dict:
    ay = copy.deepcopy(BASE["ayudas"])
    ay[tipo] = {**ay[tipo], **campos}
    return {"ayudas_respaldo": ay}


def _con_error(i: int, **campos) -> dict:
    errores = [{"descripcion": a, "ejemplo": b} for a, b in BASE["errores"]]
    errores[i] = {**errores[i], **campos}
    return {"errores_tipicos": errores}


DEFECTOS = [
    ("setup roto", {"sandbox_setup_sql": "CREATE TABLE x ("}, "sandbox_setup_sql", "setup no se pudo ejecutar"),
    ("setup con ATTACH", {"sandbox_setup_sql": BASE["esquema"] + "\nATTACH DATABASE ':memory:' AS otra;"}, "sandbox_setup_sql", "no permitida"),
    ("solución con error", {"solucion_referencia": "SELECT * FROM tabla_inexistente"}, "solucion_referencia", "no se pudo ejecutar"),
    ("solución que no es SELECT", {"solucion_referencia": "DELETE FROM libros"}, "solucion_referencia", "lectura"),
    ("solución vacía", {"solucion_referencia": ""}, "solucion_referencia", "obligatorio"),
    ("título vacío", {"titulo": ""}, "titulo", "obligatorio"),
    ("enunciado vacío", {"enunciado": ""}, "enunciado", "obligatorio"),
    ("dificultad inválida", {"dificultad": "D9"}, "dificultad", "D1, D2 o D3"),
    ("concepto inexistente", {"concepto": "no_existe"}, "concepto", "concepto"),
    ("solo 2 errores típicos", {"errores_tipicos": [{"descripcion": "a", "ejemplo": "SELECT 1"}] * 2}, "errores_tipicos", "exactamente 3"),
    ("error típico que acierta", _con_error(1, ejemplo=BASE["solucion"]), "errores_tipicos.1.ejemplo", "no es un error típico"),
    ("error típico sin ejemplo", _con_error(0, ejemplo=""), "errores_tipicos.0.ejemplo", "obligatorio"),
    ("error típico que no es SELECT", _con_error(2, ejemplo="DELETE FROM libros"), "errores_tipicos.2.ejemplo", "consulta de lectura"),
    ("AY1 con código", _con_ayuda("AY1", codigo_sql="SELECT 1"), "ayudas_respaldo.AY1.codigo_sql", "sin código"),
    ("AY1 con palabras SQL", _con_ayuda("AY1", mensaje="Usa SELECT con WHERE para filtrar."), "ayudas_respaldo.AY1.mensaje", "sin código"),
    ("AY2 con las tablas del desafío", _con_ayuda("AY2", codigo_sql="SELECT titulo FROM libros"), "ayudas_respaldo.AY2.codigo_sql", "otras tablas"),
    ("AY2 sin código", _con_ayuda("AY2", codigo_sql=None), "ayudas_respaldo.AY2.codigo_sql", "obligatorio"),
    ("AY3 con un solo ___", _con_ayuda("AY3", codigo_sql="SELECT titulo FROM libros WHERE genero = ___"), "ayudas_respaldo.AY3.codigo_sql", "___"),
    ("AY3 sin ___", _con_ayuda("AY3", codigo_sql="SELECT titulo FROM libros"), "ayudas_respaldo.AY3.codigo_sql", "___"),
    ("AY4 incorrecta", _con_ayuda("AY4", codigo_sql="SELECT titulo FROM libros"), "ayudas_respaldo.AY4.codigo_sql", "solución correcta"),
    ("ayuda sin mensaje", _con_ayuda("AY3", mensaje=""), "ayudas_respaldo.AY3.mensaje", "obligatorio"),
]


@pytest.mark.parametrize("nombre,cambios,campo,texto", DEFECTOS, ids=[d[0] for d in DEFECTOS])
def test_la_validacion_rechaza_cada_defecto(client, db, docente, nombre, cambios, campo, texto):
    problemas = _campos(client, docente, **cambios)
    assert campo in problemas, problemas
    assert texto.lower() in problemas[campo].lower()
    antes = db.scalar(select(func.count()).select_from(Desafio))
    r = client.post(RUTA, json=payload(**cambios), headers=docente)  # y no se guarda
    assert r.status_code == 422 and r.json()["error"] is True
    assert campo in {d["campo"] for d in r.json()["detalles"]}
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(Desafio)) == antes


def test_un_setup_sin_fin_no_cuelga_el_servidor(client, docente, monkeypatch):
    import app.modules.docente.validacion as v

    monkeypatch.setattr(v, "TIEMPO_MAX_PRUEBA_SEG", 0.3)
    setup = BASE["esquema"] + "\nWITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) INSERT INTO libros(id_libro,titulo,autor,genero,anio,copias_disponibles) SELECT x,'a','b','c',1,1 FROM c;"
    problemas = _campos(client, docente, sandbox_setup_sql=setup)
    assert "sandbox_setup_sql" in problemas


def test_varios_problemas_se_listan_juntos(client, docente):
    problemas = _campos(client, docente, titulo="", concepto="x", dificultad="", solucion_referencia="")
    assert {"titulo", "concepto", "dificultad", "solucion_referencia"} <= set(problemas)


def test_titulo_repetido(client, docente):
    problemas = _campos(client, docente, titulo=BASE["titulo"].upper())
    assert "titulo" in problemas and "título" in problemas["titulo"]


def test_el_cuerpo_vacio_da_422_con_problemas_y_no_500(client, docente):
    r = client.post(RUTA, json={}, headers=docente)
    assert r.status_code == 422 and len(r.json()["detalles"]) >= 5


# ---------- CRUD ----------
def test_crear_y_ver_detalle_completo(client, docente):
    r = client.post(RUTA, json=payload(), headers=docente)
    assert r.status_code == 201, r.text
    j = r.json()
    assert j["activo"] is True and j["n_sesiones"] == 0 and j["concepto"]["codigo"] == "filtrado"
    assert j["tiempo_referencia_seg"] > 0  # el de reglas.json
    assert j["solucion_referencia"] == BASE["solucion"] and len(j["errores_tipicos"]) == 3
    assert set(j["ayudas_respaldo"]) == {"AY1", "AY2", "AY3", "AY4"} and j["ayudas_respaldo"]["AY1"]["codigo_sql"] is None
    assert client.get(f"{RUTA}/{j['id']}", headers=docente).json()["titulo"] == "Novelas del club de lectura"


def test_tiempo_de_referencia_explicito(client, docente):
    r = client.post(RUTA, json=payload(tiempo_referencia_seg=777), headers=docente)
    assert r.json()["tiempo_referencia_seg"] == 777


def test_el_desafio_creado_aparece_en_la_lista_del_estudiante(client, docente, estudiante):
    antes = client.get(f"{API}/desafios", headers=estudiante).json()["total"]
    nuevo = client.post(RUTA, json=payload(), headers=docente).json()
    lista = client.get(f"{API}/desafios", headers=estudiante).json()
    assert lista["total"] == antes + 1
    assert nuevo["id"] in [d["id"] for g in lista["grupos"] for d in g["desafios"]]
    visto = client.get(f"{API}/desafios/{nuevo['id']}", headers=estudiante)
    assert visto.status_code == 200
    for secreto in (nuevo["solucion_referencia"], "INSERT INTO"):
        assert secreto not in visto.text


def test_listar_con_filtros(client, docente):
    client.post(RUTA, json=payload(), headers=docente)
    todos = client.get(RUTA, headers=docente).json()
    assert todos["total"] == len(DESAFIOS) + 1 and all("solucion_referencia" not in d for d in todos["desafios"])
    assert client.get(RUTA, params={"concepto": "filtrado"}, headers=docente).json()["total"] >= 2
    assert client.get(RUTA, params={"dificultad": "D3"}, headers=docente).json()["total"] == sum(d["dificultad"] == "D3" for d in DESAFIOS)
    assert client.get(RUTA, params={"q": "club de lectura"}, headers=docente).json()["total"] == 1
    assert client.get(RUTA, params={"q": "%"}, headers=docente).json()["total"] == 0
    assert client.get(RUTA, params={"estado": "inactivos"}, headers=docente).json()["total"] == 0
    assert client.get(RUTA, params={"estado": "otro"}, headers=docente).status_code == 422


def test_editar_cambia_los_campos_y_permite_el_propio_titulo(client, docente):
    did = client.post(RUTA, json=payload(), headers=docente).json()["id"]
    r = client.put(f"{RUTA}/{did}", json=payload(enunciado="Nuevo enunciado", dificultad="D2"), headers=docente)
    assert r.status_code == 200, r.text
    assert r.json()["enunciado"] == "Nuevo enunciado" and r.json()["dificultad"] == "D2"
    r = client.put(f"{RUTA}/{did}", json=payload(titulo=BASE["titulo"]), headers=docente)  # el de otro desafío
    assert r.status_code == 422
    assert client.put(f"{RUTA}/9999", json=payload(), headers=docente).status_code == 404
    assert client.get(f"{RUTA}/9999", headers=docente).status_code == 404


# ---------- Integridad ----------
def _usar(client, db, estudiante, did: int) -> None:
    assert client.post(f"{API}/desafios/{did}/iniciar", headers=estudiante).status_code == 200
    client.post(f"{API}/desafios/{did}/intentos", json={"codigo": "SELECT titulo FROM libros"}, headers=estudiante)


def test_desactivar_oculta_al_estudiante_sin_perder_su_historial(client, db, docente, estudiante):
    did = client.post(RUTA, json=payload(), headers=docente).json()["id"]
    _usar(client, db, estudiante, did)
    r = client.post(f"{RUTA}/{did}/desactivar", headers=docente)
    assert r.status_code == 200 and "historial" in r.json()["mensaje"]
    lista = client.get(f"{API}/desafios", headers=estudiante).json()
    assert did not in [d["id"] for g in lista["grupos"] for d in g["desafios"]]
    assert client.get(f"{API}/desafios/{did}", headers=estudiante).status_code == 404
    # el historial sigue ahí
    db.expire_all()
    assert db.scalar(select(func.count()).select_from(SesionDesafio).where(SesionDesafio.desafio_id == did)) == 1
    assert db.scalar(select(func.count()).select_from(Intento)) >= 1
    intentos = client.get(f"{API}/progreso/intentos", headers=estudiante).json()
    assert any(i["desafio_id"] == did for i in intentos["intentos"])
    # el docente lo sigue viendo, inactivo, y puede reactivarlo
    fila = next(d for d in client.get(RUTA, headers=docente).json()["desafios"] if d["id"] == did)
    assert fila["activo"] is False and fila["n_sesiones"] == 1
    assert client.post(f"{RUTA}/{did}/activar", headers=docente).status_code == 200
    assert client.get(f"{API}/desafios/{did}", headers=estudiante).status_code == 200


def test_no_se_borra_un_desafio_con_sesiones(client, db, docente, estudiante):
    did = client.post(RUTA, json=payload(), headers=docente).json()["id"]
    _usar(client, db, estudiante, did)
    r = client.delete(f"{RUTA}/{did}", headers=docente)
    assert r.status_code == 409 and "Desactívalo" in r.json()["mensaje"]
    assert client.get(f"{RUTA}/{did}", headers=docente).status_code == 200


def test_borrado_fisico_si_no_tiene_sesiones(client, docente):
    did = client.post(RUTA, json=payload(), headers=docente).json()["id"]
    assert client.delete(f"{RUTA}/{did}", headers=docente).status_code == 200
    assert client.get(f"{RUTA}/{did}", headers=docente).status_code == 404
    assert client.delete(f"{RUTA}/{did}", headers=docente).status_code == 404


def test_cambiar_solucion_o_setup_de_uno_usado_pide_confirmacion(client, db, docente, estudiante):
    did = client.post(RUTA, json=payload(), headers=docente).json()["id"]
    nueva = BASE["solucion"].replace("SELECT", "select", 1)  # equivalente: no rompe AY3 ni AY4
    # cambio no crítico en uno usado: no pide nada
    _usar(client, db, estudiante, did)
    assert client.put(f"{RUTA}/{did}", json=payload(enunciado="Otro texto"), headers=docente).status_code == 200
    # cambio crítico sin confirmar: 409 y no se guarda
    r = client.put(f"{RUTA}/{did}", json=payload(solucion_referencia=nueva), headers=docente)
    assert r.status_code == 409 and "Confirma" in r.json()["mensaje"] and "la solución" in r.json()["mensaje"]
    assert client.get(f"{RUTA}/{did}", headers=docente).json()["solucion_referencia"] == BASE["solucion"]
    # confirmado: se guarda
    r = client.put(f"{RUTA}/{did}", json=payload(solucion_referencia=nueva, confirmar_cambio=True), headers=docente)
    assert r.status_code == 200 and r.json()["solucion_referencia"] == nueva
    # el setup también lo pide
    setup = BASE["esquema"] + "\n" + BASE["datos"].strip() + "\n"
    r = client.put(f"{RUTA}/{did}", json=payload(solucion_referencia=nueva, sandbox_setup_sql=setup + "-- nota"), headers=docente)
    assert r.status_code == 409 and "el setup" in r.json()["mensaje"]


def test_cambiar_la_solucion_de_uno_sin_sesiones_no_pide_confirmacion(client, docente):
    did = client.post(RUTA, json=payload(), headers=docente).json()["id"]
    nueva = BASE["solucion"].replace("SELECT", "select", 1)  # equivalente: no rompe AY3 ni AY4
    assert client.put(f"{RUTA}/{did}", json=payload(solucion_referencia=nueva), headers=docente).status_code == 200


def test_una_edicion_invalida_no_toca_el_desafio_guardado(client, docente):
    did = client.post(RUTA, json=payload(), headers=docente).json()["id"]
    r = client.put(f"{RUTA}/{did}", json=payload(solucion_referencia="SELECT * FROM nada"), headers=docente)
    assert r.status_code == 422
    assert client.get(f"{RUTA}/{did}", headers=docente).json()["solucion_referencia"] == BASE["solucion"]
