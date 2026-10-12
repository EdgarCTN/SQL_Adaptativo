import json
import re

import pytest
from sqlalchemy import func, select

from app.core.reglas import cargar_reglas
from app.modules.desafios.models import Desafio
from app.modules.desafios.sandbox import evaluar_consulta
from app.modules.desafios.seeds import DESAFIOS, sembrar_desafios
from app.seeds.seed import RUTA_CUESTIONARIO, sembrar_todo
from conftest import API, cabecera, registrar, token_de

PARES = {
    "D1": {"filtrado", "ordenamiento"},
    "D2": {"join", "having"},
    "D3": {"subconsulta", "funciones_ventana"},
}


def _todos(db):
    return list(db.scalars(select(Desafio).order_by(Desafio.id)))


def test_seeds_idempotentes_dos_por_dificultad(client, db):
    sembrar_todo(db)
    sembrar_desafios(db)
    assert db.scalar(select(func.count()).select_from(Desafio)) == 6
    por_dif: dict[str, set] = {}
    from app.modules.desafios.models import Concepto

    for d in _todos(db):
        por_dif.setdefault(d.dificultad, set()).add(db.get(Concepto, d.concepto_id).codigo)
    assert por_dif == PARES
    assert all(d.activo for d in _todos(db))


def test_tiempo_de_referencia_sale_de_reglas_json(client, db):
    tiempos = cargar_reglas()["tiempo_referencia_seg"]
    for d in _todos(db):
        assert d.tiempo_referencia_seg == tiempos[d.dificultad]


def test_cada_solucion_pasa_por_el_sandbox(client, db):
    for d in _todos(db):
        r = evaluar_consulta(d.sandbox_setup_sql, d.solucion_referencia, d.solucion_referencia)
        assert r.correcto, (d.titulo, r.mensaje, r.detalle_tecnico)
        assert r.total_filas >= 1


def test_el_esquema_mostrado_esta_en_el_setup(client, db):
    for d in _todos(db):
        assert d.sandbox_setup_sql.startswith(d.esquema_sql)
        assert "INSERT INTO" not in d.esquema_sql


def test_cada_desafio_tiene_tres_errores_tipicos_que_fallan(client, db):
    for d in _todos(db):
        assert len(d.errores_tipicos) == 3
        for e in d.errores_tipicos:
            assert e["descripcion"]
            r = evaluar_consulta(d.sandbox_setup_sql, d.solucion_referencia, e["ejemplo"])
            assert not r.correcto, (d.titulo, e["ejemplo"])


def test_ayudas_de_respaldo(client, db):
    for d in _todos(db):
        ay = d.ayudas_respaldo
        assert set(ay) == {"AY1", "AY2", "AY3", "AY4"}
        assert all(ay[k]["mensaje"] for k in ay)
        # AY1: sin código
        assert ay["AY1"]["codigo_sql"] is None and "```" not in ay["AY1"]["mensaje"]
        # AY2: ejemplo de otro dominio (no usa las tablas del desafío)
        tablas = re.findall(r"CREATE TABLE (\w+)", d.esquema_sql)
        assert ay["AY2"]["codigo_sql"]
        for t in tablas:
            assert not re.search(rf"\b{t}\b", ay["AY2"]["codigo_sql"]), (d.titulo, t)
        # AY3: al menos 2 espacios ___ y no es una solución válida
        assert ay["AY3"]["codigo_sql"].count("___") >= 2
        assert not evaluar_consulta(d.sandbox_setup_sql, d.solucion_referencia, ay["AY3"]["codigo_sql"]).correcto
        # AY4: la solución explicada
        assert evaluar_consulta(d.sandbox_setup_sql, d.solucion_referencia, ay["AY4"]["codigo_sql"]).correcto
        assert len(ay["AY4"]["mensaje"]) > 40


def test_no_repite_los_items_del_cuestionario():
    datos = json.loads(RUTA_CUESTIONARIO.read_text(encoding="utf-8-sig"))
    texto = json.dumps(datos, ensure_ascii=False).lower()
    norm = lambda s: re.sub(r"\s+", " ", s.lower()).strip().rstrip(";")  # noqa: E731
    for d in DESAFIOS:
        assert norm(d["solucion"]) not in texto
        assert norm(d["enunciado"]) not in texto
        # dominio distinto: ninguna tabla del cuestionario
        assert not re.search(r"\b(clientes|pedidos|productos)\b", d["esquema"].lower())


def test_api_lista_y_detalle_de_los_desafios_sembrados(client):
    registrar(client)
    h = cabecera(token_de(client))
    j = client.get(f"{API}/desafios", headers=h).json()
    assert j["total"] == 6 and [len(g["desafios"]) for g in j["grupos"]] == [2, 2, 2]
    assert len(j["conceptos"]) == 6
    for g in j["grupos"]:
        for item in g["desafios"]:
            r = client.get(f"{API}/desafios/{item['id']}", headers=h)
            assert r.status_code == 200 and r.json()["esquema_sql"] and r.json()["recursos"]
            for clave in ("solucion_referencia", "ayudas_respaldo", "sandbox_setup_sql", "errores_tipicos"):
                assert clave not in r.json()


@pytest.mark.parametrize("indice", range(6))
def test_recorrido_completo_por_api(client, db, indice):
    registrar(client)
    h = cabecera(token_de(client))
    d = _todos(db)[indice]
    client.post(f"{API}/desafios/{d.id}/iniciar", headers=h)
    mal = client.post(
        f"{API}/desafios/{d.id}/intentos", json={"codigo": d.errores_tipicos[0]["ejemplo"]}, headers=h
    ).json()
    assert mal["correcto"] is False and mal["numero"] == 1
    bien = client.post(f"{API}/desafios/{d.id}/intentos", json={"codigo": d.solucion_referencia}, headers=h).json()
    assert bien["correcto"] and bien["resultado_cierre"] == "SA" and bien["numero"] == 2
