from sqlalchemy import func, select

from app.modules.auth.models import Usuario
from app.modules.motor_retiro.mensajes import MensajeEstudiante
from app.modules.notificaciones.models import Notificacion
from app.modules.notificaciones.service import registrar_mensajes
from conftest import API, cabecera, registrar, token_de
from test_entrega8_banderas_oferta import enviar, iniciar, preparar


def _usuario(db, correo: str) -> Usuario:
    return db.scalar(select(Usuario).where(Usuario.correo == correo))


def test_un_evento_del_motor_no_crea_notificaciones_duplicadas(client, db):
    registrar(client)
    usuario = _usuario(db, "ana@uni.edu")
    mensaje = MensajeEstudiante("recaida", "recaida", "Recuperamos un poco de apoyo.", regla="R3")

    registrar_mensajes(db, usuario.id, "sesion:42:cierre", (mensaje,))
    registrar_mensajes(db, usuario.id, "sesion:42:cierre", (mensaje,))

    cantidad = db.scalar(select(func.count()).select_from(Notificacion))
    assert cantidad == 1
    notificacion = db.scalar(select(Notificacion))
    assert notificacion.tipo == "recaida" and notificacion.regla == "R3"


def test_reflexion_r10_se_persiste_como_notificacion_del_envio(client, db):
    headers, desafio_id = preparar(client, db)
    iniciar(client, headers, desafio_id)

    salidas = [enviar(client, headers, desafio_id) for _ in range(3)]

    assert salidas[-1]["reflexion"]["tipo"] == "reflexion"
    notificaciones = list(db.scalars(select(Notificacion).where(Notificacion.usuario_id == _usuario(db, "ana@uni.edu").id)))
    assert len(notificaciones) == 1
    assert notificaciones[0].tipo == "reflexion" and notificaciones[0].regla == "R10"


def test_notificaciones_solo_se_listan_y_marcan_por_su_dueno(client, db):
    registrar(client, correo="ana@uni.edu")
    registrar(client, nombre="Bea", correo="bea@uni.edu")
    ana = _usuario(db, "ana@uni.edu")
    db.add(Notificacion(
        usuario_id=ana.id, tipo="retiro", texto="Tu ayuda cambió.", regla="R1", leida=False,
        clave_evento="sesion:9:cierre:0",
    ))
    db.commit()
    notificacion = db.scalar(select(Notificacion))
    id_notificacion = notificacion.id
    ana_headers = cabecera(token_de(client, "ana@uni.edu"))
    bea_headers = cabecera(token_de(client, "bea@uni.edu"))

    propia = client.get(f"{API}/notificaciones", headers=ana_headers)
    ajena = client.get(f"{API}/notificaciones", headers=bea_headers)
    assert propia.status_code == 200
    assert propia.json()["no_leidas"] == 1 and len(propia.json()["notificaciones"]) == 1
    assert ajena.status_code == 200 and ajena.json()["notificaciones"] == []
    assert client.post(f"{API}/notificaciones/{id_notificacion}/leida", headers=bea_headers).status_code == 404
    assert client.post(f"{API}/notificaciones/{id_notificacion}/leida", headers=ana_headers).json() == {
        "ok": True, "id": id_notificacion,
    }
    assert client.get(f"{API}/notificaciones", headers=ana_headers).json()["no_leidas"] == 0


def test_marcar_todas_como_leidas(client, db):
    registrar(client)
    usuario = _usuario(db, "ana@uni.edu")
    for indice in range(2):
        db.add(Notificacion(
            usuario_id=usuario.id, tipo="refuerzo", texto="Te acompañamos un poco más.", regla="R5",
            leida=False, clave_evento=f"sesion:11:cierre:{indice}",
        ))
    db.commit()
    headers = cabecera(token_de(client))

    respuesta = client.post(f"{API}/notificaciones/leer-todas", headers=headers)

    assert respuesta.status_code == 200 and respuesta.json() == {"ok": True, "actualizadas": 2}
    assert client.get(f"{API}/notificaciones", headers=headers).json()["no_leidas"] == 0
