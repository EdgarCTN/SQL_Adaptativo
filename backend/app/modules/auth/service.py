from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errores import ErrorApp
from app.core.seguridad import HASH_FALSO, crear_token, hashear_password, verificar_password
from app.core.db import ahora_utc
from app.modules.auth.models import Rol, TokenRevocado, Usuario
from app.modules.auth.schemas import PerfilIn, RegistroIn

MSG_CREDENCIALES = "El correo o la contraseña no son válidos."
MSG_DUPLICADO = "Ya existe una cuenta con ese correo."


def normalizar_correo(correo: str) -> str:
    return correo.strip().lower()


def _validar_dominio(correo: str) -> None:
    dominios = settings.dominios_permitidos
    if dominios and correo.rpartition("@")[2] not in dominios:
        lista = ", ".join(f"@{d}" for d in dominios)
        raise ErrorApp(f"Usa tu correo institucional ({lista}).", 422)


def registrar_estudiante(db: Session, datos: RegistroIn) -> Usuario:
    """El registro público SIEMPRE crea un estudiante."""
    correo = normalizar_correo(datos.correo)
    _validar_dominio(correo)
    if db.scalar(select(Usuario.id).where(Usuario.correo == correo)):
        raise ErrorApp(MSG_DUPLICADO, 409)
    usuario = Usuario(
        nombre=datos.nombre,
        correo=correo,
        hash_password=hashear_password(datos.contrasena),
        rol=Rol.estudiante.value,
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ErrorApp(MSG_DUPLICADO, 409)
    return usuario


def autenticar(db: Session, correo: str, contrasena: str) -> tuple[Usuario, str, int]:
    usuario = db.scalar(select(Usuario).where(Usuario.correo == normalizar_correo(correo)))
    if usuario is None:
        verificar_password(contrasena, HASH_FALSO)  # iguala tiempos de respuesta
        raise ErrorApp(MSG_CREDENCIALES, 401)
    if not verificar_password(contrasena, usuario.hash_password) or not usuario.activo:
        raise ErrorApp(MSG_CREDENCIALES, 401)
    token, segundos = crear_token(usuario.id, usuario.rol)
    return usuario, token, segundos


def actualizar_perfil(db: Session, usuario: Usuario, datos: PerfilIn) -> Usuario:
    # Se valida todo antes de modificar nada (CU01 EX4).
    if datos.contrasena_nueva is not None and not verificar_password(
        datos.contrasena_actual or "", usuario.hash_password
    ):
        raise ErrorApp("Contraseña actual: no es correcta.", 422)
    if datos.nombre is not None:
        usuario.nombre = datos.nombre
    if datos.contrasena_nueva is not None:
        usuario.hash_password = hashear_password(datos.contrasena_nueva)
    db.add(usuario)
    db.commit()
    return usuario


def token_esta_revocado(db: Session, jti: str | None) -> bool:
    if not jti:
        return False
    return db.scalar(select(TokenRevocado.id).where(TokenRevocado.jti == jti)) is not None


def revocar_token(db: Session, payload: dict) -> None:
    """Registra el jti hasta que el token venza y limpia los registros ya vencidos."""
    jti = payload.get("jti")
    if jti and not token_esta_revocado(db, jti):
        expira = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
        db.add(TokenRevocado(jti=jti, expira_en=expira))
    db.execute(delete(TokenRevocado).where(TokenRevocado.expira_en < ahora_utc()))
    try:
        db.commit()
    except IntegrityError:  # dos logout simultáneos: el otro ya lo registró
        db.rollback()
