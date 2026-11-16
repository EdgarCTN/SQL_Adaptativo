from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.admin import service
from app.modules.admin.schemas import CambioRolIn, CambioUsuarioOut, ListaUsuariosOut
from app.modules.auth.deps import requiere_rol
from app.modules.auth.models import Rol, Usuario

# La misma dependencia en el router y en cada ruta: FastAPI la ejecuta una sola vez por solicitud.
solo_administrador = requiere_rol(Rol.administrador)

router = APIRouter(
    prefix="/admin/usuarios",
    tags=["Administración"],
    dependencies=[Depends(solo_administrador)],
)

IdUsuario = Annotated[int, Path(ge=1, le=2**31 - 1)]  # el tope evita desbordar el entero de SQLite


@router.get("", response_model=ListaUsuariosOut)
def listar(
    q: str | None = Query(default=None, max_length=100),
    rol: str | None = Query(default=None, pattern="^(estudiante|docente|administrador)$"),
    pagina: int = Query(default=1, ge=1),
    tam: int = Query(default=20, ge=1, le=service.TAM_MAXIMO),
    db: Session = Depends(get_db),
):
    return service.listar(db, q, rol, pagina, tam)


@router.put("/{usuario_id}/rol", response_model=CambioUsuarioOut)
def cambiar_rol(
    usuario_id: IdUsuario,
    datos: CambioRolIn,
    admin: Usuario = Depends(solo_administrador),
    db: Session = Depends(get_db),
):
    return service.cambiar_rol(db, admin, usuario_id, datos.rol)


@router.post("/{usuario_id}/activar", response_model=CambioUsuarioOut)
def activar(usuario_id: IdUsuario, admin: Usuario = Depends(solo_administrador), db: Session = Depends(get_db)):
    return service.cambiar_activo(db, admin, usuario_id, True)


@router.post("/{usuario_id}/desactivar", response_model=CambioUsuarioOut)
def desactivar(usuario_id: IdUsuario, admin: Usuario = Depends(solo_administrador), db: Session = Depends(get_db)):
    return service.cambiar_activo(db, admin, usuario_id, False)
