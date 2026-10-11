import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errores import ErrorApp
from app.core.seguridad import decodificar_token
from app.modules.auth.models import Rol, Usuario

_bearer = HTTPBearer(auto_error=False)
_CABECERA = {"WWW-Authenticate": "Bearer"}


def usuario_actual(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    if cred is None:
        raise ErrorApp("Necesitas iniciar sesión para continuar.", 401, _CABECERA)
    try:
        payload = decodificar_token(cred.credentials)
        usuario = db.get(Usuario, int(payload["sub"]))
    except (jwt.PyJWTError, ValueError):
        raise ErrorApp("Tu sesión no es válida o expiró. Inicia sesión de nuevo.", 401, _CABECERA)
    if usuario is None or not usuario.activo:
        raise ErrorApp("Tu sesión no es válida o expiró. Inicia sesión de nuevo.", 401, _CABECERA)
    return usuario


def requiere_rol(*roles: Rol | str):
    permitidos = {r.value if isinstance(r, Rol) else r for r in roles}

    def dependencia(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if usuario.rol not in permitidos:
            raise ErrorApp("No tienes permiso para acceder a esta función.", 403)
        return usuario

    return dependencia
