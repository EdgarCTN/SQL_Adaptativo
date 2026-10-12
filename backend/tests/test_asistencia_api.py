import json

import pytest
from sqlalchemy import select

from app.main import app
from app.modules.asistencia.config_llm import cargar_llm, cargar_mensajes_fijos
from app.modules.asistencia.llm.base import LLMProvider, RespuestaLLM
from app.modules.asistencia.models import SolicitudAyuda, ValoracionAyuda
from app.modules.asistencia.router import get_proveedor
from app.modules.desafios.models import Desafio, SesionDesafio
from app.modules.linea_base.models import NivelSoporte
from app.modules.motor_retiro.niveles import NS_POR_DEFECTO  # noqa: F401
from conftest import API, cabecera, registrar, token_de
from test_desafios import SOLUCION, crear_desafio

MALA = "SELECT titulo FROM libros"  # falla: no coincide
CFG = cargar_llm()
AVISO_AY4 = cargar_mensajes_fijos()["mensajes"]["solucion_ya_mostrada"]["texto"]


class Falso(LLMProvider):
    """Devuelve el tipo pedido en JSON válido; permite programar respuestas."""

    nombre = "falso"

    def __init__(self, respuestas=None, excepcion=None):
        self.llamadas: list = []
        self.respuestas = list(respuestas or [])
        self.excepcion = excepcion

    def generar(self, solicitud):
        self.llamadas.append(solicitud)
        if self.excepcion:
            raise self.excepcion
        if self.respuestas:
            texto = self.respuestas.pop(0)
        else:
            texto = json.dumps({"tipo_entregado": solicitud.tipo_ayuda, "mensaje": f"Ayuda {solicitud.tipo_ayuda}", "codigo_sql": None})
        return RespuestaLLM(texto, self.nombre, False, (CFG["etiqueta_ia"],))


@pytest.fixture
def falso():
    f = Falso()
    app.dependency_overrides[get_proveedor] = lambda: f
    yield f
    app.dependency_overrides.pop(get_proveedor, None)


def _ana(db):
    from app.modules.auth.models import Usuario

    return db.scalar(select(Usuario).where(Usuario.correo == "ana@uni.edu"))


def preparar(client, db):
    registrar(client)
    h = cabecera(token_de(client))
    did = crear_desafio(db)
    return h, did


def iniciar(client, h, did):
    client.post(f"{API}/desafios/{did}/iniciar", headers=h)


def intentar(client, h, did, codigo=MALA):
    return client.post(f"{API}/desafios/{did}/intentos", json={"codigo": codigo}, headers=h).json()


def ayuda(client, h, did, **cuerpo):
    return client.post(f"{API}/desafios/{did}/ayuda", json=cuerpo, headers=h)


@pytest.fixture(autouse=True)
def _sin_sembrados(client, db):
    db.execute(Desafio.__table__.delete())
    db.commit()


def test_sin_sesion_o_desafio_inexistente(client, db, falso):
    h, did = preparar(client, db)
    r = ayuda(client, h, did)
    assert r.status_code == 409 and "inicia el desafío" in r.json()["mensaje"]
    assert ayuda(client, h, 9999).status_code == 404
    assert client.post(f"{API}/desafios/{did}/ayuda").status_code == 401
    assert falso.llamadas == []


def test_primera_ayuda_ay1_se_registra_y_lleva_etiqueta(client, db, falso):
    h, did = preparar(client, db)
    iniciar(client, h, did)
    r = ayuda(client, h, did, mensaje_estudiante="no sé por dónde empezar")
    j = r.json()
    assert r.status_code == 200 and j["tipo_ayuda"] == "AY1" and j["mensaje"] == "Ayuda AY1"
    assert j["etiquetas"] == [CFG["etiqueta_ia"]] and j["fue_respaldo"] is False and j["aviso"] is None
    s = db.scalar(select(SolicitudAyuda))
    assert (s.tipo_ayuda, s.proveedor, s.fue_respaldo, s.incidente_validacion) == ("AY1", "falso", False, None)
    assert s.momento is not None and s.texto_entregado == "Ayuda AY1" and s.id == j["solicitud_id"]
    # el LLM recibió el mensaje del estudiante y nada de la solución ni de la identidad
    p = falso.llamadas[0]
    assert "no sé por dónde empezar" in p.mensaje_usuario
    junto = p.prompt_sistema + p.mensaje_usuario
    assert SOLUCION not in junto and "<solucion_referencia>" not in junto
    u = _ana(db)
    assert u.correo == "ana@uni.edu" and u.correo not in junto and u.nombre not in junto and "Pérez" not in junto


def test_escalada_hasta_ay4_marca_nr_y_luego_solo_recuerda(client, db, falso):
    h, did = preparar(client, db)
    iniciar(client, h, did)
    assert ayuda(client, h, did).json()["tipo_ayuda"] == "AY1"
    r = ayuda(client, h, did).json()  # sin fallo nuevo: repite reformulada
    assert r["tipo_ayuda"] == "AY1" and r["reformulada"] is True
    assert "ya entregada" in falso.llamadas[-1].mensaje_usuario  # recibió la ayuda previa para reformular
    intentar(client, h, did)
    r = ayuda(client, h, did).json()
    assert r["tipo_ayuda"] == "AY2" and r["reformulada"] is False
    intentar(client, h, did)  # 2 fallos
    assert ayuda(client, h, did).json()["tipo_ayuda"] == "AY3"
    intentar(client, h, did)  # 3 fallos
    j = ayuda(client, h, did).json()
    assert j["tipo_ayuda"] == "AY4" and j["aviso"] == AVISO_AY4 and j["desafio_marcado_nr"] is True
    ses = db.scalar(select(SesionDesafio))
    db.refresh(ses)
    assert ses.resultado_cierre == "NR" and ses.estado == "en_curso"  # NR de inmediato
    # pedir más tras AY4: solo el recordatorio, sin LLM ni registro nuevo
    n_llamadas, n_filas = len(falso.llamadas), len(list(db.scalars(select(SolicitudAyuda))))
    j = ayuda(client, h, did).json()
    assert j["tipo_ayuda"] is None and j["mensaje"] is None and j["aviso"] == AVISO_AY4 and j["desafio_marcado_nr"]
    assert len(falso.llamadas) == n_llamadas and len(list(db.scalars(select(SolicitudAyuda)))) == n_filas
    # si luego lo resuelve, sigue NR y no cuenta como resuelto
    ok = intentar(client, h, did, SOLUCION)
    assert ok["correcto"] and ok["resultado_cierre"] == "NR"
    lista = client.get(f"{API}/desafios", headers=h).json()
    assert lista["grupos"][0]["desafios"][0]["estado"] == "sin_iniciar"
    assert client.get(f"{API}/desafios/{did}", headers=h).json()["estado"] == "sin_iniciar"


def test_cierre_con_ayuda_cp_ce_y_sa(client, db, falso):
    h, did = preparar(client, db)
    # NS por defecto = 1: AY1 es la ayuda prevista → CP
    iniciar(client, h, did)
    ayuda(client, h, did)
    assert intentar(client, h, did, SOLUCION)["resultado_cierre"] == "CP"
    # AY1 + AY2 (más de lo previsto) → CE
    iniciar(client, h, did)
    ayuda(client, h, did)
    intentar(client, h, did)
    assert ayuda(client, h, did).json()["tipo_ayuda"] == "AY2"
    assert intentar(client, h, did, SOLUCION)["resultado_cierre"] == "CE"
    # sin ayuda → SA
    iniciar(client, h, did)
    assert intentar(client, h, did, SOLUCION)["resultado_cierre"] == "SA"


def test_el_ns_de_niveles_soporte_define_la_primera_ayuda_y_los_minimos(client, db, falso):
    h, did = preparar(client, db)
    from app.modules.desafios.models import Concepto
    u = _ana(db)
    c = db.scalar(select(Concepto).where(Concepto.codigo == "filtrado"))
    db.add(NivelSoporte(usuario_id=u.id, concepto_id=c.id, ns=3, ns_maximo_historico=3))
    db.commit()
    iniciar(client, h, did)
    j = ayuda(client, h, did).json()  # NS3 → AY3, pero sin 2 fallos baja a AY2 y se sugiere reintentar
    assert j["tipo_ayuda"] == "AY2" and j["sugerencia"]
    intentar(client, h, did)
    intentar(client, h, did)
    assert ayuda(client, h, did).json()["tipo_ayuda"] == "AY3"


def test_ns3_con_ayuda_ay3_es_cp(client, db, falso):
    h, did = preparar(client, db)
    from app.modules.desafios.models import Concepto
    u = _ana(db)
    c = db.scalar(select(Concepto).where(Concepto.codigo == "filtrado"))
    db.add(NivelSoporte(usuario_id=u.id, concepto_id=c.id, ns=2, ns_maximo_historico=2))
    db.commit()
    iniciar(client, h, did)
    assert ayuda(client, h, did).json()["tipo_ayuda"] == "AY2"
    assert intentar(client, h, did, SOLUCION)["resultado_cierre"] == "CP"


# ---------- Fallos del LLM: siempre ayuda de respaldo ----------
def _comprobar_respaldo(client, db, h, did, j, incidente_contiene):
    assert j["tipo_ayuda"] == "AY1" and j["fue_respaldo"] is True
    assert j["etiquetas"] == [CFG["etiqueta_ia"], CFG["etiqueta_mock"]]
    assert j["mensaje"] == "SECRETO_AYUDA" and j["codigo_sql"] is None  # el respaldo guardado en el desafío
    s = db.scalar(select(SolicitudAyuda))
    assert s.proveedor == "respaldo" and s.fue_respaldo and incidente_contiene in s.incidente_validacion


def test_error_del_llm_entrega_el_respaldo_sin_error_tecnico(client, db):
    f = Falso(excepcion=RuntimeError("API caída"))
    app.dependency_overrides[get_proveedor] = lambda: f
    try:
        h, did = preparar(client, db)
        # crear_desafio guarda ayudas_respaldo con un texto de prueba
        iniciar(client, h, did)
        r = ayuda(client, h, did)
        assert r.status_code == 200 and "API caída" not in r.text and "Traceback" not in r.text
        _comprobar_respaldo(client, db, h, did, r.json(), "RuntimeError")
        assert len(f.llamadas) == 2  # intento + un reintento
    finally:
        app.dependency_overrides.pop(get_proveedor, None)


@pytest.mark.parametrize(
    "respuestas,motivo",
    [
        (["no es json", "tampoco"], "V1"),
        ([json.dumps({"tipo_entregado": "AY4", "mensaje": "x", "codigo_sql": None})] * 2, "V2"),
        ([json.dumps({"tipo_entregado": "AY1", "mensaje": "  ", "codigo_sql": None})] * 2, "V1"),
    ],
)
def test_respuesta_invalida_dos_veces_cae_al_respaldo_y_registra_el_incidente(client, db, respuestas, motivo):
    f = Falso(respuestas)
    app.dependency_overrides[get_proveedor] = lambda: f
    try:
        h, did = preparar(client, db)
        iniciar(client, h, did)
        j = ayuda(client, h, did).json()
        _comprobar_respaldo(client, db, h, did, j, motivo)
    finally:
        app.dependency_overrides.pop(get_proveedor, None)


def test_un_reintento_con_el_motivo_puede_salvar_la_ayuda(client, db):
    valida = json.dumps({"tipo_entregado": "AY1", "mensaje": "Segunda vez bien", "codigo_sql": None})
    f = Falso(["basura", valida])
    app.dependency_overrides[get_proveedor] = lambda: f
    try:
        h, did = preparar(client, db)
        iniciar(client, h, did)
        j = ayuda(client, h, did).json()
        assert j["mensaje"] == "Segunda vez bien" and j["fue_respaldo"] is False
        assert len(f.llamadas) == 2 and "CORRECCIÓN" in f.llamadas[1].mensaje_usuario and "V1" in f.llamadas[1].mensaje_usuario
        assert "CORRECCIÓN" not in f.llamadas[0].mensaje_usuario
        s = db.scalar(select(SolicitudAyuda))
        assert s.proveedor == "falso" and s.incidente_validacion.startswith("V1")
    finally:
        app.dependency_overrides.pop(get_proveedor, None)


def test_con_el_proveedor_mock_por_defecto_la_ayuda_sale_de_respaldo_con_ambas_etiquetas(client, db):
    h, did = preparar(client, db)
    iniciar(client, h, did)
    j = ayuda(client, h, did).json()
    assert j["tipo_ayuda"] == "AY1" and j["fue_respaldo"] is True and j["mensaje"]
    assert j["etiquetas"] == [CFG["etiqueta_ia"], CFG["etiqueta_mock"]]


@pytest.mark.parametrize("guardado,esperado", [("texto simple", "texto simple"), (None, None), ({"AY1": 5}, None), ({"AY1": {}}, None)])
def test_respaldo_mal_guardado_no_rompe_la_ayuda(client, db, guardado, esperado):
    f = Falso(excepcion=RuntimeError("caída"))
    app.dependency_overrides[get_proveedor] = lambda: f
    try:
        h, did = preparar(client, db)
        d = db.get(Desafio, did)
        d.ayudas_respaldo = {"AY1": guardado} if isinstance(guardado, str) else guardado
        db.commit()
        iniciar(client, h, did)
        r = ayuda(client, h, did)
        assert r.status_code == 200 and r.json()["fue_respaldo"] is True and r.json()["mensaje"]
        if esperado:
            assert r.json()["mensaje"] == esperado
    finally:
        app.dependency_overrides.pop(get_proveedor, None)


# ---------- Valoración ----------
def test_valoracion_se_registra_y_se_puede_cambiar(client, db, falso):
    h, did = preparar(client, db)
    iniciar(client, h, did)
    sid = ayuda(client, h, did).json()["solicitud_id"]
    r = client.post(f"{API}/ayudas/{sid}/valoracion", json={"valor": 1}, headers=h)
    assert r.status_code == 200 and r.json() == {"ok": True, "valor": 1}
    client.post(f"{API}/ayudas/{sid}/valoracion", json={"valor": -1}, headers=h)
    filas = list(db.scalars(select(ValoracionAyuda)))
    assert len(filas) == 1 and filas[0].valor == -1


@pytest.mark.parametrize("cuerpo", [{"valor": 0}, {"valor": 2}, {"valor": "x"}, {}])
def test_valoracion_invalida_422(client, db, falso, cuerpo):
    h, did = preparar(client, db)
    iniciar(client, h, did)
    sid = ayuda(client, h, did).json()["solicitud_id"]
    r = client.post(f"{API}/ayudas/{sid}/valoracion", json=cuerpo, headers=h)
    assert r.status_code == 422 and r.json()["error"] is True
    assert db.scalar(select(ValoracionAyuda.id)) is None


def test_valoracion_ajena_o_inexistente_404_y_requiere_sesion(client, db, falso):
    h, did = preparar(client, db)
    iniciar(client, h, did)
    sid = ayuda(client, h, did).json()["solicitud_id"]
    registrar(client, "Luis", "luis@uni.edu", "Clave12345")
    h2 = cabecera(token_de(client, "luis@uni.edu"))
    assert client.post(f"{API}/ayudas/{sid}/valoracion", json={"valor": 1}, headers=h2).status_code == 404
    assert client.post(f"{API}/ayudas/9999/valoracion", json={"valor": 1}, headers=h).status_code == 404
    assert client.post(f"{API}/ayudas/{sid}/valoracion", json={"valor": 1}).status_code == 401
    assert db.scalar(select(ValoracionAyuda.id)) is None
