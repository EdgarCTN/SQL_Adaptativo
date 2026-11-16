from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class UsuarioAdminOut(BaseModel):
    """Solo para el administrador: nunca incluye el hash de la contraseña."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    correo: str
    rol: str
    activo: bool
    creado_en: datetime


class ListaUsuariosOut(BaseModel):
    total: int
    pagina: int
    tam: int
    paginas: int
    usuarios: list[UsuarioAdminOut]


class CambioRolIn(BaseModel):
    rol: Literal["estudiante", "docente", "administrador"]


class CambioUsuarioOut(BaseModel):
    ok: bool = True
    mensaje: str
    usuario: UsuarioAdminOut
