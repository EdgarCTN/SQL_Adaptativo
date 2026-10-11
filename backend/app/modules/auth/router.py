from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth import service
from app.modules.auth.deps import usuario_actual
from app.modules.auth.models import Usuario
from app.modules.auth.schemas import (
    LoginIn,
    MensajeOut,
    PerfilIn,
    RegistroIn,
    TokenOut,
    UsuarioOut,
)

router = APIRouter(prefix="/auth", tags=["Autenticación"])
perfil_router = APIRouter(prefix="/perfil", tags=["Perfil"])


@router.post("/registro", response_model=UsuarioOut, status_code=201)
def registro(datos: RegistroIn, db: Session = Depends(get_db)):
    return service.registrar_estudiante(db, datos)


@router.post("/login", response_model=TokenOut)
def login(datos: LoginIn, db: Session = Depends(get_db)):
    usuario, token, segundos = service.autenticar(db, datos.correo, datos.contrasena)
    return TokenOut(access_token=token, expira_en=segundos, usuario=UsuarioOut.model_validate(usuario))


@router.post("/logout", response_model=MensajeOut)
def logout(_: Usuario = Depends(usuario_actual)):
    # Sin revocación en el servidor: el cliente descarta el token (ver DECISIONES).
    return MensajeOut(mensaje="Sesión cerrada.")


@router.get("/yo", response_model=UsuarioOut)
def yo(usuario: Usuario = Depends(usuario_actual)):
    return usuario


@perfil_router.get("", response_model=UsuarioOut)
def ver_perfil(usuario: Usuario = Depends(usuario_actual)):
    return usuario


@perfil_router.put("", response_model=UsuarioOut)
def editar_perfil(
    datos: PerfilIn, usuario: Usuario = Depends(usuario_actual), db: Session = Depends(get_db)
):
    return service.actualizar_perfil(db, usuario, datos)
