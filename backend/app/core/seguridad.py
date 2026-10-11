"""Hash de contraseñas (argon2) y tokens JWT."""
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import settings

ALGORITMO = "HS256"
_ph = PasswordHasher()
HASH_FALSO = _ph.hash("contrasena-que-nadie-usa")  # para igualar tiempos si el correo no existe


def hashear_password(password: str) -> str:
    return _ph.hash(password)


def verificar_password(password: str, hash_guardado: str) -> bool:
    try:
        return _ph.verify(hash_guardado, password)
    except (VerificationError, InvalidHashError):
        return False


def crear_token(usuario_id: int, rol: str, minutos: int | None = None) -> tuple[str, int]:
    """Devuelve (token, segundos de vigencia). `minutos` puede ser negativo (pruebas)."""
    minutos = settings.access_token_expire_minutes if minutos is None else minutos
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario_id),
        "rol": rol,
        "jti": uuid.uuid4().hex,  # listo para una futura revocación
        "iat": ahora,
        "exp": ahora + timedelta(minutes=minutos),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITMO), minutos * 60


def decodificar_token(token: str) -> dict:
    """Lanza jwt.PyJWTError si el token es inválido o expiró."""
    return jwt.decode(
        token, settings.secret_key, algorithms=[ALGORITMO], options={"require": ["exp", "sub"]}
    )
