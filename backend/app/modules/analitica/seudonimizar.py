"""Seudónimos para reportes: id_pseudonimo = HMAC-SHA256(usuario_id) con ANON_SALT, truncado. Nunca nombre ni correo."""
import hashlib
import hmac
import logging
import secrets

import pandas as pd

from app.core.config import settings

log = logging.getLogger("app.analitica")

LONGITUD = 16  # caracteres hexadecimales (64 bits)
COLUMNAS_PERSONALES = frozenset({"nombre", "correo", "email", "contrasena", "hash_contrasena", "password"})
_temporal: list[str] = []


def _sal(sal: str | None) -> bytes:
    valor = (settings.anon_salt if sal is None else sal).strip()
    if not valor:  # sin ANON_SALT la app no falla: sal temporal (los seudónimos cambian al reiniciar)
        if not _temporal:
            _temporal.append(secrets.token_hex(32))
            log.warning("ANON_SALT está vacía: se usa una sal temporal y los seudónimos no serán estables entre reinicios")
        valor = _temporal[0]
    return valor.encode("utf-8")


def id_pseudonimo(usuario_id: int, sal: str | None = None) -> str:
    return hmac.new(_sal(sal), str(int(usuario_id)).encode("ascii"), hashlib.sha256).hexdigest()[:LONGITUD]


def seudonimizar_df(df: pd.DataFrame, columna: str = "usuario_id", sal: str | None = None) -> pd.DataFrame:
    """Copia con `id_pseudonimo` en lugar de `usuario_id`; descarta además cualquier columna personal."""
    salida = df.drop(columns=[c for c in df.columns if c in COLUMNAS_PERSONALES]).copy()
    if columna in salida.columns:
        ids = [id_pseudonimo(u, sal) for u in salida[columna]]
        salida = salida.drop(columns=[columna])
        salida.insert(0, "id_pseudonimo", ids)
    return salida
