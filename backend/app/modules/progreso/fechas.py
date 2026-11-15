"""Filtros de fecha del historial: texto → datetime UTC, con errores 422 en español.

Acepta `AAAA-MM-DD` o una fecha y hora ISO (con `Z` u offset). Sin zona horaria se toma UTC. Una fecha sin hora vale
desde las 00:00:00 en `desde` y hasta las 23:59:59.999999 en `hasta`, para que el último día quede completo.
"""
from datetime import date, datetime, time, timezone

from app.core.errores import ErrorApp

MSG_FECHA_INVALIDA = "La fecha de {campo} no es válida. Usa el formato AAAA-MM-DD (por ejemplo, 2026-11-15)."
MSG_RANGO_INVERTIDO = "La fecha de inicio no puede ser posterior a la fecha de fin."
_ETIQUETA = {"desde": "inicio", "hasta": "fin"}


def _error(campo: str) -> ErrorApp:
    return ErrorApp(
        MSG_FECHA_INVALIDA.format(campo=_ETIQUETA[campo]), 422,
        extra={"detalles": [{"campo": campo, "mensaje": "Fecha no válida."}]},
    )


def interpretar_fecha(valor: str | None, campo: str) -> datetime | None:
    """`campo` es «desde» o «hasta». Texto vacío o ausente = sin filtro."""
    texto = (valor or "").strip()
    if not texto:
        return None
    try:
        if len(texto) == 10:  # AAAA-MM-DD
            dia = date.fromisoformat(texto)
            hora = time.min if campo == "desde" else time.max
            return datetime.combine(dia, hora, tzinfo=timezone.utc)
        f = datetime.fromisoformat(texto.replace("Z", "+00:00").replace("z", "+00:00"))
        return f.replace(tzinfo=timezone.utc) if f.tzinfo is None else f.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise _error(campo) from None


def interpretar_rango(desde: str | None, hasta: str | None) -> tuple[datetime | None, datetime | None]:
    d, h = interpretar_fecha(desde, "desde"), interpretar_fecha(hasta, "hasta")
    if d is not None and h is not None and d > h:
        raise ErrorApp(
            MSG_RANGO_INVERTIDO, 422,
            extra={"detalles": [{"campo": "desde", "mensaje": MSG_RANGO_INVERTIDO}]},
        )
    return d, h
