"""Errores de la API: siempre JSON {error: true, mensaje} en español, sin stack trace."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app.errores")

MSG_INESPERADO = "Ocurrió un problema inesperado. Inténtalo de nuevo en unos minutos."

_HTTP = {
    401: "Necesitas iniciar sesión para continuar.",
    403: "No tienes permiso para realizar esta acción.",
    404: "No encontramos lo que buscas.",
    405: "Esa operación no está permitida en esta dirección.",
}

_ETIQUETAS = {
    "nombre": "Nombre",
    "correo": "Correo",
    "contrasena": "Contraseña",
    "contrasena_actual": "Contraseña actual",
    "contrasena_nueva": "Contraseña nueva",
}


class ErrorApp(Exception):
    """Error controlado, con mensaje apto para mostrar al usuario."""

    def __init__(
        self,
        mensaje: str,
        status_code: int = 400,
        headers: dict | None = None,
        extra: dict | None = None,
    ):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status_code = status_code
        self.headers = headers
        self.extra = extra or {}


def _respuesta(status: int, mensaje: str, headers: dict | None = None, **extra) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": True, "mensaje": mensaje, **extra}, headers=headers
    )


def _traducir(err: dict) -> tuple[str, str]:
    """Devuelve (campo, mensaje en español) para un error de Pydantic."""
    tipo, msg, ctx = err.get("type", ""), err.get("msg", ""), err.get("ctx") or {}
    loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
    campo = loc[-1] if loc else ""
    if tipo == "missing":
        texto = "Este campo es obligatorio." if campo else "Falta el cuerpo de la solicitud."
    elif tipo == "string_too_short":
        texto = f"Debe tener al menos {ctx.get('min_length')} caracteres."
    elif tipo == "string_too_long":
        texto = f"No puede superar los {ctx.get('max_length')} caracteres."
    elif tipo == "json_invalid":
        texto = "El cuerpo de la solicitud no es un JSON válido."
    elif tipo in ("model_attributes_type", "dict_type", "model_type"):
        texto = "El cuerpo de la solicitud no tiene el formato esperado."
    elif tipo == "value_error":
        if msg.startswith("value is not a valid email"):
            texto = "No tiene un formato de correo válido."
        else:
            texto = msg.removeprefix("Value error, ")
    else:
        texto = "El valor ingresado no es válido."
    return campo, texto


def registrar_manejadores(app: FastAPI) -> None:
    @app.exception_handler(ErrorApp)
    async def _app(_: Request, exc: ErrorApp):
        return _respuesta(exc.status_code, exc.mensaje, exc.headers, **exc.extra)

    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, exc: RequestValidationError):
        detalles = []
        for e in exc.errors():
            campo, texto = _traducir(e)
            detalles.append({"campo": campo, "mensaje": texto})
        partes = [
            f"{_ETIQUETAS.get(d['campo'], d['campo'])}: {d['mensaje']}" if d["campo"] else d["mensaje"]
            for d in detalles
        ]
        return _respuesta(422, "Revisa los datos: " + " ".join(partes), detalles=detalles)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        mensaje = _HTTP.get(exc.status_code, "No se pudo completar la solicitud.")
        return _respuesta(exc.status_code, mensaje, getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _inesperado(_: Request, exc: Exception):
        log.exception("Error no controlado", exc_info=exc)
        return _respuesta(500, MSG_INESPERADO)
