import json
import re

import pytest
from sqlalchemy import func, select

from app.core.reglas import cargar_reglas
from app.modules.desafios.models import Desafio
from app.modules.desafios.sandbox import evaluar_consulta
from app.modules.desafios.seeds import DESAFIOS, sembrar_desafios
from app.seeds.seed import CONCEPTOS, PRERREQUISITOS, RUTA_CUESTIONARIO, sembrar_todo
from conftest import API, cabecera, registrar, token_de

# Dificultades esperadas por concepto. Los segundos desafíos (entregas 3B y 3C) tienen una dificultad distinta
# a la del primero, para que R8 pueda ofrecer «un desafío más básico del mismo concepto».
DIFICULTADES = {
    "filtrado": ["D1", "D2"],
    "ordenamiento": ["D1", "D2"],
    "join": ["D1", "D2"],
    "conteo_agregacion": ["D1"],
    "group_by": ["D2"],
    "having": ["D1", "D2"],
    "left_join": ["D2"],
    "subconsulta": ["D2", "D3"],
    "funciones_ventana": ["D2", "D3"],
    "join_agregacion": ["D3"],
}
TOTAL = sum(len(v) for v in DIFICULTADES.values())  # 16 tras la entrega 3C


CODIGOS_CONCEPTOS = [c for c, _ in CONCEPTOS]


def _todos(db):
    return list(db.scalars(select(Desafio).order_by(Desafio.id)))


def test_seeds_idempotentes_dieciseis_desafios_con_los_10_conceptos(client, db):
    from app.modules.desafios.models import Concepto

    sembrar_todo(db)
    sembrar_desafios(db)
    sembrar_desafios(db)  # idempotente por título: sembrar de nuevo no duplica
    assert db.scalar(select(func.count()).select_from(Desafio)) == TOTAL == 16
    por_concepto: dict[str, list] = {}
    for d in _todos(db):
        por_concepto.setdefault(db.get(Concepto, d.concepto_id).codigo, []).append(d.dificultad)
    assert {c: sorted(v) for c, v in por_concepto.items()} == DIFICULTADES
    # los 10 conceptos tienen al menos un desafío
    assert sorted(por_concepto) == sorted(CODIGOS_CONCEPTOS) and len(por_concepto) == 10
    assert all(d.activo for d in _todos(db))


def test_segundos_desafios_tienen_dificultad_distinta_a_la_del_primero(client, db):
    from app.modules.desafios.models import Concepto

    por_concepto: dict[str, list] = {}
    for d in _todos(db):  # en orden de creación: el primero sembrado de cada concepto va primero
        por_concepto.setdefault(db.get(Concepto, d.concepto_id).codigo, []).append(d.dificultad)
    for codigo in ("filtrado", "ordenamiento", "join", "having", "subconsulta", "funciones_ventana"):
        assert len(por_concepto[codigo]) == 2, codigo
        assert por_concepto[codigo][0] != por_concepto[codigo][1], codigo


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
    assert j["total"] == 16 and [len(g["desafios"]) for g in j["grupos"]] == [5, 8, 3]
    assert len(j["conceptos"]) == 10
    for codigo, esperado in (("left_join", 1), ("filtrado", 2), ("ordenamiento", 2), ("join", 2), ("having", 2), ("subconsulta", 2), ("funciones_ventana", 2)):
        r = client.get(f"{API}/desafios", params={"concepto": codigo}, headers=h).json()
        assert r["total"] == esperado, codigo
    for g in j["grupos"]:
        for item in g["desafios"]:
            r = client.get(f"{API}/desafios/{item['id']}", headers=h)
            assert r.status_code == 200 and r.json()["esquema_sql"] and r.json()["recursos"]
            for clave in ("solucion_referencia", "ayudas_respaldo", "sandbox_setup_sql", "errores_tipicos"):
                assert clave not in r.json()


@pytest.mark.parametrize("indice", range(TOTAL))
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


def test_titulos_unicos_y_tiempo_por_dificultad(client, db):
    titulos = [d.titulo for d in _todos(db)]
    assert len(titulos) == len(set(titulos))
    assert len({d["titulo"] for d in DESAFIOS}) == len(DESAFIOS) == TOTAL


def test_prerrequisitos_cadena_completa_y_sin_ciclos(client, db):
    from app.modules.desafios.models import Concepto

    sembrar_todo(db)
    por_id = {c.id: c for c in db.scalars(select(Concepto))}
    por_codigo = {c.codigo: c for c in por_id.values()}
    assert set(PRERREQUISITOS) == set(por_codigo) and len(por_codigo) == 10
    # Solo el concepto de entrada no tiene prerrequisito
    sin_previo = [c.codigo for c in por_id.values() if c.prerrequisito_id is None]
    assert sin_previo == ["filtrado"]
    for c in por_id.values():
        esperado = PRERREQUISITOS[c.codigo]
        assert (por_id[c.prerrequisito_id].codigo if c.prerrequisito_id else None) == esperado
        # sin ciclos: toda cadena llega a «filtrado»
        visto, actual = set(), c
        while actual.prerrequisito_id is not None:
            assert actual.id not in visto
            visto.add(actual.id)
            actual = por_id[actual.prerrequisito_id]
        assert actual.codigo == "filtrado"


def test_prerrequisitos_se_completan_en_base_existente_sin_pisar_valores(client, db):
    from app.modules.desafios.models import Concepto

    sembrar_todo(db)
    por_codigo = {c.codigo: c for c in db.scalars(select(Concepto))}
    por_codigo["having"].prerrequisito_id = None  # base vieja: sin mapa
    por_codigo["join"].prerrequisito_id = por_codigo["ordenamiento"].id  # valor ya definido a mano
    db.commit()
    sembrar_todo(db)
    db.expire_all()
    por_codigo = {c.codigo: c for c in db.scalars(select(Concepto))}
    assert por_codigo["having"].prerrequisito_id == por_codigo["group_by"].id
    assert por_codigo["join"].prerrequisito_id == por_codigo["ordenamiento"].id
