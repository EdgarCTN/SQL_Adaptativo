"""R14 Inactividad (Matriz, Tabla 9, bloque 6). Decisiones puras: no tocan la base de datos.

≥ 14 días sin actividad (la última sesión de desafío del estudiante) → el NS de cada concepto sube 1 sin superar
`ns_maximo_historico`. Umbral (reglas.json): r14_inactividad.dias. La parte con base de datos está en motor.evaluar_inactividad.
"""
from datetime import datetime, timedelta, timezone

from app.modules.motor_retiro.niveles import NS_MAXIMO


def a_utc(f: datetime) -> datetime:
    return f.replace(tzinfo=timezone.utc) if f.tzinfo is None else f


def esta_inactivo(ultima_actividad: datetime | None, ahora: datetime, dias: int) -> bool:
    """Sin ninguna sesión (None) no hay actividad que retomar: no se considera inactivo."""
    return ultima_actividad is not None and a_utc(ahora) - a_utc(ultima_actividad) >= timedelta(days=int(dias))


def ns_tras_inactividad(ns: int, ns_maximo_historico: int) -> int:
    """Sube 1 sin superar el máximo histórico (ni el NS máximo); nunca baja."""
    return max(ns, min(ns + 1, int(ns_maximo_historico), NS_MAXIMO))
