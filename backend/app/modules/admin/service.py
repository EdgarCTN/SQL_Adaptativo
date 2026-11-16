"""Administración de usuarios (entrega 13A): listar, cambiar rol y activar o desactivar cuentas."""
import logging
from math import ceil

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errores import ErrorApp
from app.modules.admin.auditoria import registrar_auditoria
from app.modules.auth.models import Rol, Usuario

log = logging.getLogger("app.admin")

TAM_MAXIMO = 100
MSG_NO_EXISTE = "No encontramos a ese usuario."
MSG_PROPIO_ROL = "No puedes cambiar tu propio rol. Pídele a otro administrador que lo haga."
MSG_PROPIA_CUENTA = "No puedes desactivar tu propia cuenta. Pídele a otro administrador que lo haga."
MSG_ULTIMO_ADMIN = "Debe quedar al menos un administrador activo. Nombra a otro administrador antes de hacer este cambio."
MSG_ERROR_GUARDADO = "No pudimos guardar el cambio. Inténtalo de nuevo en unos segundos."


def _obtener(db: Session, usuario_id: int) -> Usuario:
    u = db.get(Usuario, usuario_id)
    if u is None:
        raise ErrorApp(MSG_NO_EXISTE, 404)
    return u


def _hay_otro_administrador_activo(db: Session, excluir_id: int) -> bool:
    n = db.scalar(
        select(func.count())
        .select_from(Usuario)
        .where(Usuario.rol == Rol.administrador.value, Usuario.activo.is_(True), Usuario.id != excluir_id)
    )
    return (n or 0) > 0


def _confirmar(db: Session) -> None:
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        log.exception("No se pudo guardar el cambio de usuario")
        raise ErrorApp(MSG_ERROR_GUARDADO, 503)


def _respuesta(u: Usuario, mensaje: str) -> dict:
    return {"ok": True, "mensaje": mensaje, "usuario": u}


def listar(db: Session, q: str | None, rol: str | None, pagina: int, tam: int) -> dict:
    filtros = []
    if rol:
        filtros.append(Usuario.rol == rol)
    if q and q.strip():
        texto = q.strip().lower()
        filtros.append(
            func.lower(Usuario.nombre).contains(texto, autoescape=True)
            | func.lower(Usuario.correo).contains(texto, autoescape=True)
        )
    total = db.scalar(select(func.count()).select_from(Usuario).where(*filtros)) or 0
    paginas = max(1, ceil(total / tam))
    pagina = min(pagina, paginas)  # una página fuera de rango devuelve la última
    filas = db.scalars(
        select(Usuario)
        .where(*filtros)
        .order_by(func.lower(Usuario.nombre), Usuario.id)
        .offset((pagina - 1) * tam)
        .limit(tam)
    ).all()
    return {"total": total, "pagina": pagina, "tam": tam, "paginas": paginas, "usuarios": list(filas)}


def cambiar_rol(db: Session, admin: Usuario, usuario_id: int, rol: str) -> dict:
    u = _obtener(db, usuario_id)
    if u.id == admin.id:
        raise ErrorApp(MSG_PROPIO_ROL, 409)
    if u.rol == rol:
        return _respuesta(u, f"Ese usuario ya tiene el rol {rol}.")
    if u.rol == Rol.administrador.value and u.activo and not _hay_otro_administrador_activo(db, u.id):
        raise ErrorApp(MSG_ULTIMO_ADMIN, 409)
    anterior = u.rol
    u.rol = rol
    # La auditoría viaja en la misma transacción: o se guardan el cambio y su registro, o ninguno.
    registrar_auditoria(
        db, admin.id, "usuario.cambiar_rol", f"usuario:{u.id}", {"rol_anterior": anterior, "rol_nuevo": rol}, confirmar=False
    )
    _confirmar(db)
    return _respuesta(u, f"Rol actualizado: ahora es {rol}.")


def cambiar_activo(db: Session, admin: Usuario, usuario_id: int, activo: bool) -> dict:
    u = _obtener(db, usuario_id)
    if not activo and u.id == admin.id:
        raise ErrorApp(MSG_PROPIA_CUENTA, 409)
    if bool(u.activo) == activo:
        return _respuesta(u, "La cuenta ya estaba activa." if activo else "La cuenta ya estaba desactivada.")
    if not activo and u.rol == Rol.administrador.value and not _hay_otro_administrador_activo(db, u.id):
        raise ErrorApp(MSG_ULTIMO_ADMIN, 409)
    u.activo = activo
    registrar_auditoria(
        db, admin.id, "usuario.activar" if activo else "usuario.desactivar", f"usuario:{u.id}", {"rol": u.rol}, confirmar=False
    )
    _confirmar(db)
    return _respuesta(
        u, "Cuenta activada." if activo else "Cuenta desactivada: no podrá iniciar sesión hasta que la actives de nuevo."
    )
