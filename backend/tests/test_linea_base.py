import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.seguridad import hashear_password
from app.modules.auth.models import Rol, Usuario
from app.modules.desafios.models import Concepto
from app.modules.linea_base.models import (
    Consentimiento,
    LineaBaseCuestionario,
    LineaBaseRespuesta,
    NivelSoporte,
    Omision,
)
from app.seeds.seed import RUTA_CUESTIONARIO, sembrar_cuestionario
from conftest import API, cabecera, registrar, token_de

LB = f"{API}/linea-base"


def _contar(db, modelo) -> int:
    return db.scalar(select(func.count()).select_from(modelo))


def _sesion(client):
    registrar(client)
    return cabecera(token_de(client))


def _consentir(client, h):
    assert client.post(f"{LB}/consentimiento", json={"acepta": True}, headers=h).status_code == 200


def _cuestionario(client, h) -> dict:
    r = client.get(f"{LB}/cuestionario", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _payload_valido(cuestionario: dict) -> dict:
    """Respuestas completas construidas solo con lo que sirve la API (sin `correcta`)."""
    resp = []
    for parte in cuestionario["partes"]:
        for p in parte["preguntas"]:
            if "tipo" in p:  # partes 1 y 3
                resp.append({"pregunta_id": p["id"], "opciones": [p["opciones"][0]["id"]]})
            else:  # parte 2: opción a con confianza 3
                resp.append({"pregunta_id": p["id"], "opciones": ["a"], "confianza": 3})
    return {"cuestionario_id": cuestionario["id"], "respuestas": resp}


def _con(payload, pregunta_id, **cambios):
    nuevo = json.loads(json.dumps(payload))
    for r in nuevo["respuestas"]:
        if r["pregunta_id"] == pregunta_id:
            r.update(cambios)
    return nuevo


def _enviar(client, h, payload):
    return client.post(f"{LB}/respuestas", json=payload, headers=h)


def _vacio(db) -> bool:
    return all(_contar(db, m) == 0 for m in (LineaBaseRespuesta, Omision, NivelSoporte))


# ---------- estado y consentimiento ----------
def test_estado_inicial(client):
    h = _sesion(client)
    r = client.get(f"{LB}/estado", headers=h)
    assert r.status_code == 200
    j = r.json()
    assert j["siguiente_paso"] == "consentimiento"
    assert j["linea_base_completada"] is False and j["consentimiento_aceptado"] is False
    assert j["cuestionario_disponible"] is True


def test_endpoints_requieren_sesion_y_rol_estudiante(client, db):
    assert client.get(f"{LB}/estado").status_code == 401
    db.add(Usuario(nombre="Doc", correo="doc@uni.edu", hash_password=hashear_password("Clave12345"), rol=Rol.docente.value))
    db.commit()
    h = cabecera(token_de(client, "doc@uni.edu", "Clave12345"))
    for ruta in ("/estado", "/cuestionario"):
        assert client.get(f"{LB}{ruta}", headers=h).status_code == 403


def test_no_aceptar_consentimiento_no_guarda_nada(client, db):
    h = _sesion(client)
    r = client.post(f"{LB}/consentimiento", json={"acepta": False}, headers=h)
    assert r.status_code == 200 and r.json()["aceptado"] is False
    assert "necesario" in r.json()["mensaje"]
    assert _contar(db, Consentimiento) == 0
    assert client.get(f"{LB}/estado", headers=h).json()["siguiente_paso"] == "consentimiento"


def test_aceptar_consentimiento_guarda_fecha_y_version_una_sola_vez(client, db):
    h = _sesion(client)
    for _ in range(2):
        r = client.post(f"{LB}/consentimiento", json={"acepta": True}, headers=h)
        assert r.status_code == 200 and r.json()["aceptado"] is True
        assert r.json()["version"] and r.json()["aceptado_en"]
    assert _contar(db, Consentimiento) == 1
    assert client.get(f"{LB}/estado", headers=h).json()["siguiente_paso"] == "cuestionario"


def test_consentimiento_cuerpo_invalido(client):
    h = _sesion(client)
    r = client.post(f"{LB}/consentimiento", json={}, headers=h)
    assert r.status_code == 422 and r.json()["error"] is True


# ---------- cuestionario ----------
def test_cuestionario_exige_consentimiento(client):
    h = _sesion(client)
    r = client.get(f"{LB}/cuestionario", headers=h)
    assert r.status_code == 403 and "consentimiento" in r.json()["mensaje"]


def test_cuestionario_servido_nunca_contiene_correcta(client):
    h = _sesion(client)
    _consentir(client, h)
    r = client.get(f"{LB}/cuestionario", headers=h)
    assert r.status_code == 200
    assert "correcta" not in r.text
    c = r.json()
    assert [p["id"] for p in c["partes"]] == ["parte1", "parte2", "parte3"]
    assert len(c["partes"][1]["preguntas"]) == 11
    assert c["partes"][1]["preguntas"][0]["opciones"][-1]["es_no_se"] is True


def test_cuestionario_no_disponible_mensaje_controlado(client, db):
    h = _sesion(client)
    _consentir(client, h)
    for c in db.scalars(select(LineaBaseCuestionario)):
        c.activo = False
    db.commit()
    r = client.get(f"{LB}/cuestionario", headers=h)
    assert r.status_code == 503 and r.json()["error"] is True
    assert "no puede presentarse" in r.json()["mensaje"]
    e = client.get(f"{LB}/estado", headers=h).json()
    assert e["cuestionario_disponible"] is False and e["siguiente_paso"] == "no_disponible"


def test_seed_cuestionario_idempotente_y_conserva_correcta(client, db):
    sembrar_cuestionario(db)
    sembrar_cuestionario(db)
    filas = list(db.scalars(select(LineaBaseCuestionario)))
    assert len(filas) == 1 and filas[0].version == 1 and filas[0].activo is True
    original = json.loads(Path(RUTA_CUESTIONARIO).read_text(encoding="utf-8-sig"))
    assert filas[0].contenido == original
    assert "correcta" in json.dumps(filas[0].contenido)  # en BD se conserva para el cálculo (3B)


# ---------- envío de respuestas ----------
def test_respuestas_sin_consentimiento_no_guardan_nada(client, db):
    h = _sesion(client)
    # payload armado desde el JSON de la BD porque aún no se puede pedir el cuestionario
    contenido = db.scalar(select(LineaBaseCuestionario)).contenido
    from app.modules.linea_base.service import quitar_clave

    payload = _payload_valido({"id": 1, "partes": quitar_clave(contenido)["partes"]})
    r = _enviar(client, h, payload)
    assert r.status_code == 403
    assert _vacio(db)
    assert db.scalar(select(Usuario).where(Usuario.correo == "ana@uni.edu")).linea_base_completada is False


def test_respuestas_completas_guardan_y_marcan_completada(client, db):
    h = _sesion(client)
    _consentir(client, h)
    r = _enviar(client, h, _payload_valido(_cuestionario(client, h)))
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["linea_base_completada"] is True and "nivel inicial" in j["mensaje"]
    assert _contar(db, LineaBaseRespuesta) == 23  # 6 + 11 + 6
    assert _contar(db, Omision) == 0
    assert _contar(db, NivelSoporte) == _contar(db, Concepto) == 10
    assert set(db.scalars(select(NivelSoporte.ns))) == {2}  # todo erróneo con confianza 3 → m 0.275 → NS2
    assert db.scalar(select(Usuario).where(Usuario.correo == "ana@uni.edu")).linea_base_completada is True
    assert client.get(f"{LB}/estado", headers=h).json()["siguiente_paso"] == "completado"
    assert client.get(f"{API}/auth/yo", headers=h).json()["linea_base_completada"] is True
    # ya completado: no se puede repetir ni volver a pedir el cuestionario
    assert _enviar(client, h, _payload_valido(_cuestionario_bd(db))).status_code == 409
    assert client.get(f"{LB}/cuestionario", headers=h).status_code == 409
    assert _contar(db, LineaBaseRespuesta) == 23


def _cuestionario_bd(db) -> dict:
    from app.modules.linea_base.service import quitar_clave

    c = db.scalar(select(LineaBaseCuestionario))
    return {"id": c.id, "partes": quitar_clave(c.contenido)["partes"]}


def test_respuestas_guardadas_tienen_el_formato_esperado(client, db):
    h = _sesion(client)
    _consentir(client, h)
    payload = _payload_valido(_cuestionario(client, h))
    payload = _con(payload, "1.2", opciones=["a", "c"])
    payload = _con(payload, "P2", opciones=["e"], confianza=None)  # «No sé»
    assert _enviar(client, h, payload).status_code == 200
    filas = {f.pregunta_id: f for f in db.scalars(select(LineaBaseRespuesta))}
    assert filas["1.2"].opciones == ["a", "c"] and filas["1.2"].parte == 1 and filas["1.2"].confianza is None
    assert filas["P1"].opciones == ["a"] and filas["P1"].confianza == 3 and filas["P1"].parte == 2
    assert filas["P2"].es_no_se is True and filas["P2"].confianza is None
    assert filas["3.1"].parte == 3


def test_respuestas_vacias_listan_todas_las_pendientes(client, db):
    h = _sesion(client)
    _consentir(client, h)
    r = _enviar(client, h, {"respuestas": []})
    assert r.status_code == 422
    j = r.json()
    assert j["error"] is True and len(j["detalles"]) == 23
    assert j["detalles"][0] == {"campo": "1.1", "mensaje": "Falta responder esta pregunta."}
    assert _vacio(db)


def test_respuestas_incompletas_indican_cuales_faltan(client, db):
    h = _sesion(client)
    _consentir(client, h)
    payload = _payload_valido(_cuestionario(client, h))
    payload["respuestas"] = [r for r in payload["respuestas"] if r["pregunta_id"] not in ("1.4", "P7", "3.6")]
    r = _enviar(client, h, payload)
    assert r.status_code == 422
    assert r.json()["preguntas_con_problema"] == ["1.4", "P7", "3.6"]
    assert _vacio(db)


@pytest.mark.parametrize(
    "pregunta,cambios",
    [
        ("1.2", {"opciones": ["a", "h"]}),  # «Ninguna» excluye a las demás
        ("1.3", {"opciones": ["g", "a"]}),  # «Ninguno» excluye a las demás
        ("1.2", {"opciones": []}),
        ("1.3", {"opciones": ["a", "a"]}),
        ("1.1", {"opciones": ["a", "b"]}),  # única con dos opciones
        ("1.1", {"opciones": ["zz"]}),
        ("1.1", {"opciones": ["a"], "confianza": 3}),
        ("3.1", {"opciones": ["a"], "omitir": "muy_facil"}),
        ("P1", {"confianza": None}),  # respuesta sin confianza
        ("P1", {"confianza": 6}),
        ("P1", {"confianza": 0}),
        ("P1", {"opciones": []}),  # ni respuesta, ni «No sé», ni omisión
        ("P1", {"opciones": ["z"]}),
        ("P1", {"opciones": ["a", "b"]}),
        ("P1", {"omitir": "aburrida"}),
        ("P1", {"omitir": "muy_facil"}),  # omitir y responder a la vez
    ],
)
def test_respuestas_invalidas_se_rechazan_por_pregunta(client, db, pregunta, cambios):
    h = _sesion(client)
    _consentir(client, h)
    payload = _con(_payload_valido(_cuestionario(client, h)), pregunta, **cambios)
    r = _enviar(client, h, payload)
    assert r.status_code == 422, r.text
    assert r.json()["preguntas_con_problema"] == [pregunta]
    assert _vacio(db)


def test_no_se_no_pide_confianza_y_omisiones_se_guardan_en_omisiones(client, db):
    h = _sesion(client)
    _consentir(client, h)
    payload = _payload_valido(_cuestionario(client, h))
    payload = _con(payload, "P1", opciones=["e"], confianza=None)  # «No sé»
    payload = _con(payload, "P5", opciones=[], confianza=None, omitir="muy_facil")  # concepto join
    payload = _con(payload, "P11", opciones=[], confianza=None, omitir="muy_dificil")  # funciones_ventana
    assert _enviar(client, h, payload).status_code == 200
    assert _contar(db, LineaBaseRespuesta) == 21  # 23 menos las dos omitidas
    omis = {o.concepto_id: o for o in db.scalars(select(Omision))}
    codigo = dict(db.execute(select(Concepto.id, Concepto.codigo)).all())
    por_concepto = {codigo[k]: v for k, v in omis.items()}
    assert por_concepto["join"].motivo == "muy_facil" and por_concepto["funciones_ventana"].motivo == "muy_dificil"
    assert all(o.origen == "linea_base" and o.desafio_id is None for o in omis.values())


def test_pregunta_desconocida_o_repetida(client, db):
    h = _sesion(client)
    _consentir(client, h)
    base = _payload_valido(_cuestionario(client, h))
    extra = json.loads(json.dumps(base))
    extra["respuestas"].append({"pregunta_id": "X9", "opciones": ["a"]})
    r = _enviar(client, h, extra)
    assert r.status_code == 422 and r.json()["preguntas_con_problema"] == ["X9"]
    rep = json.loads(json.dumps(base))
    rep["respuestas"].append(dict(rep["respuestas"][0]))
    r = _enviar(client, h, rep)
    assert r.status_code == 422 and r.json()["preguntas_con_problema"] == ["1.1"]
    assert _vacio(db)


def test_cuestionario_id_desactualizado(client):
    h = _sesion(client)
    _consentir(client, h)
    payload = _payload_valido(_cuestionario(client, h))
    payload["cuestionario_id"] = 999
    assert _enviar(client, h, payload).status_code == 409


def test_error_de_guardado_es_controlado_y_permite_reintentar(client, db, monkeypatch):
    h = _sesion(client)
    _consentir(client, h)
    payload = _payload_valido(_cuestionario(client, h))

    def falla(self):
        raise OperationalError("INSERT", {}, Exception("disco lleno"))

    with monkeypatch.context() as m:
        m.setattr(Session, "commit", falla)
        r = _enviar(client, h, payload)
    assert r.status_code == 503 and r.json()["error"] is True
    assert "disco lleno" not in r.text and "inténtalo de nuevo" in r.json()["mensaje"]
    assert _vacio(db)
    assert db.scalar(select(Usuario).where(Usuario.correo == "ana@uni.edu")).linea_base_completada is False
    # el mismo envío funciona al reintentar
    assert _enviar(client, h, payload).status_code == 200
    assert _contar(db, LineaBaseRespuesta) == 23
