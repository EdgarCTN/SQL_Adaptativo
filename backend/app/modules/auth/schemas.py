from datetime import datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    model_validator,
)

Nombre = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]


def _fuerza(v: str) -> str:
    if not any(c.isalpha() for c in v) or not any(c.isdigit() for c in v):
        raise ValueError("Debe incluir al menos una letra y un número.")
    return v


Contrasena = Annotated[str, Field(min_length=8, max_length=128), AfterValidator(_fuerza)]


class RegistroIn(BaseModel):
    nombre: Nombre
    correo: EmailStr
    contrasena: Contrasena


class LoginIn(BaseModel):
    correo: str = Field(max_length=254)
    contrasena: str = Field(max_length=128)


class PerfilIn(BaseModel):
    nombre: Nombre | None = None
    contrasena_actual: str | None = Field(default=None, max_length=128)
    contrasena_nueva: Contrasena | None = None

    @model_validator(mode="after")
    def _validar(self):
        if self.nombre is None and self.contrasena_nueva is None:
            raise ValueError("Indica el nombre o la contraseña nueva que quieres actualizar.")
        if self.contrasena_nueva is not None and not self.contrasena_actual:
            raise ValueError("Para cambiar la contraseña debes indicar la contraseña actual.")
        return self


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    correo: str
    rol: str
    activo: bool
    creado_en: datetime
    linea_base_completada: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_en: int
    usuario: UsuarioOut


class MensajeOut(BaseModel):
    ok: bool = True
    mensaje: str
