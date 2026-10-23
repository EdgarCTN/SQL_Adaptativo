import hashlib
import hmac

import pandas as pd

from app.core.config import settings
from app.modules.analitica import extractores as ex
from app.modules.analitica.seudonimizar import COLUMNAS_PERSONALES, id_pseudonimo, seudonimizar_df
from conftest import API, cabecera, registrar, token_de
from test_motor_integracion import abandonar, ana, concepto, preparar, primera_ayuda  # noqa: F401


def test_seudonimo_es_hmac_estable_y_distinto_por_usuario():
    a = id_pseudonimo(1, "sal-de-prueba")
    assert a == id_pseudonimo(1, "sal-de-prueba")
    assert a == hmac.new(b"sal-de-prueba", b"1", hashlib.sha256).hexdigest()[:16]
    assert len(a) == 16 and a != id_pseudonimo(2, "sal-de-prueba") and a != id_pseudonimo(1, "otra-sal")


def test_sin_sal_se_usa_una_temporal_estable_en_el_proceso(monkeypatch):
    monkeypatch.setattr(settings, "anon_salt", "")
    assert id_pseudonimo(5) == id_pseudonimo(5) and id_pseudonimo(5) != id_pseudonimo(6)
    monkeypatch.setattr(settings, "anon_salt", "configurada")
    assert id_pseudonimo(5) == id_pseudonimo(5, "configurada")


def test_seudonimizar_df_quita_usuario_id_y_columnas_personales():
    df = pd.DataFrame({"usuario_id": [1, 2], "nombre": ["Ana", "Beto"], "correo": ["a@x", "b@x"], "ta": [0.5, 1.0]})
    s = seudonimizar_df(df, sal="s")
    assert list(s.columns) == ["id_pseudonimo", "ta"] and s["id_pseudonimo"].tolist() == [id_pseudonimo(1, "s"), id_pseudonimo(2, "s")]
    assert "usuario_id" in df.columns  # no modifica la entrada


def test_ningun_extractor_devuelve_nombre_ni_correo(client, db):
    h, did = preparar(client, db)
    for _ in range(2):
        abandonar(client, h, did)
    primera_ayuda(client, h, did)
    uid, cid = ana(db).id, concepto(db).id
    sesiones = ex.sesiones_cerradas_df(db)
    ids = [int(i) for i in sesiones["sesion_id"]]
    marcos = [
        sesiones, ex.intentos_df(db, ids), ex.ayudas_df(db, ids), ex.historial_niveles_df(db),
        ex.indicadores_historicos_df(db), ex.cierres_del_concepto(db, uid, cid),
    ]
    assert not sesiones.empty
    for df in marcos:
        assert not (set(df.columns) & COLUMNAS_PERSONALES)
        texto = df.astype(str).to_csv()
        assert "Ana Pérez" not in texto and "ana@uni.edu" not in texto
