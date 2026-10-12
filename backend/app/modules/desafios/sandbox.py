"""Sandbox SQL: SQLite en memoria, solo lectura, con tiempo límite y tope de filas.

Reglas de comparación (se anotan también en DECISIONES):
- Se comparan los VALORES del conjunto de resultados; los NOMBRES de columna se ignoran.
- El orden de las filas se ignora salvo que la solución tenga un ORDER BY de nivel superior.
- Los decimales se comparan redondeados a 6 cifras.
Dialecto: es SQLite, no PostgreSQL (diferencias en funciones y tipos).
"""
import re
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass, field

from app.core.config import settings

MAX_FILAS_GUARDADAS = 20  # filas que se conservan en intentos.resultado_obtenido
MAX_CARACTERES_CELDA = 200  # recorte de textos largos al mostrarlos
LIMITE_LONGITUD_VALOR = 1_000_000  # SQLITE_LIMIT_LENGTH: frena randomblob/zeroblob gigantes
_FUNCIONES_BLOQUEADAS = {"load_extension", "readfile", "writefile", "edit"}

MSG_CORRECTO = "¡Correcto! Tu consulta devuelve el resultado esperado."
MSG_VACIA = "Escribe tu consulta antes de enviar."
MSG_NO_PERMITIDA = (
    "Solo se permiten consultas de lectura (SELECT, o WITH seguido de SELECT). "
    "Esta operación no está permitida."
)
MSG_VARIAS = "Envía una sola sentencia SQL a la vez."
MSG_TIEMPO = "La consulta tardó demasiado y se detuvo. Revisa que no tenga ciclos o combinaciones innecesarias."
MSG_DISTINTO = {
    "columnas": "La consulta se ejecutó, pero devuelve un número de columnas distinto al esperado.",
    "filas_cantidad": "La consulta se ejecutó, pero devuelve un número de filas distinto al esperado.",
    "orden": "La consulta devuelve las filas correctas, pero en un orden distinto al pedido.",
    "contenido": "La consulta se ejecutó, pero las filas devueltas no coinciden con lo esperado.",
}


class ErrorConfiguracionDesafio(Exception):
    """El setup o la solución de referencia (de confianza) no se pueden ejecutar."""


@dataclass
class ResultadoSandbox:
    correcto: bool
    # correcto | resultado_distinto | error_sql | no_permitida | varias_sentencias | tiempo_agotado | vacia
    tipo: str
    mensaje: str
    detalle_tecnico: str | None = None
    columnas: list[str] = field(default_factory=list)
    filas: list[list] = field(default_factory=list)  # ya aptas para JSON y recortadas
    total_filas: int = 0
    truncado: bool = False

    def para_guardar(self) -> dict:
        """Versión compacta para intentos.resultado_obtenido."""
        return {
            "tipo": self.tipo,
            "mensaje": self.mensaje,
            "detalle_tecnico": self.detalle_tecnico,
            "columnas": self.columnas,
            "filas": self.filas[:MAX_FILAS_GUARDADAS],
            "total_filas": self.total_filas,
            "truncado": self.truncado or len(self.filas) > MAX_FILAS_GUARDADAS,
        }


# ---------- Análisis léxico mínimo ----------
def _enmascarar(sql: str) -> str:
    """Quita comentarios y vacía el contenido de textos e identificadores entre comillas."""
    out: list[str] = []
    i, n = 0, len(sql)
    while i < n:
        c = sql[i]
        if sql.startswith("--", i):
            j = sql.find("\n", i)
            i = n if j == -1 else j
            out.append(" ")
        elif sql.startswith("/*", i):
            j = sql.find("*/", i + 2)
            i = n if j == -1 else j + 2
            out.append(" ")
        elif c in "'\"`[":
            cierre = "]" if c == "[" else c
            j = i + 1
            while j < n:
                if sql[j] == cierre:
                    if cierre != "]" and j + 1 < n and sql[j + 1] == cierre:
                        j += 2
                        continue
                    break
                j += 1
            out.append(c + " " * (min(j, n) - i - 1) + (cierre if j < n else ""))
            i = j + 1
        else:
            out.append(c)
            i += 1
    return "".join(out)


def primera_palabra(sql: str) -> str:
    m = re.match(r"[\s(]*([A-Za-z_]+)", _enmascarar(sql))
    return m.group(1).lower() if m else ""


def tiene_order_by_superior(sql: str) -> bool:
    """True si hay un ORDER BY fuera de paréntesis (no cuenta OVER (ORDER BY ...) ni subconsultas)."""
    profundidad = 0
    for m in re.finditer(r"[()]|\border\s+by\b", _enmascarar(sql), re.IGNORECASE):
        t = m.group(0)
        if t == "(":
            profundidad += 1
        elif t == ")":
            profundidad -= 1
        elif profundidad == 0:
            return True
    return False


# ---------- Mensajes en lenguaje claro ----------
def _traducir_error(texto: str) -> str:
    t = texto.strip()
    reglas = [
        (r"no such table: (.+)", "La tabla «{0}» no existe en este desafío. Revisa los nombres en el esquema."),
        (r"no such column: (.+)", "La columna «{0}» no existe. Revisa los nombres de columna en el esquema."),
        (r"ambiguous column name: (.+)", "La columna «{0}» es ambigua: indica de qué tabla viene (tabla.columna)."),
        (r"no such function: (.+)", "La función «{0}» no existe en este motor SQL."),
        (r'near "(.+?)": syntax error', "Hay un error de sintaxis cerca de «{0}»."),
        (r"incomplete input", "La consulta parece incompleta. Revisa que no falte nada al final."),
        (r"misuse of aggregate.*", "Se usó una función de agregación donde no está permitida (por ejemplo, en WHERE)."),
        (r"aggregate functions are not allowed in the WHERE clause", "No se pueden usar funciones de agregación en WHERE."),
        (r"wrong number of arguments to function (.+)\(\)", "La función «{0}» recibe un número distinto de argumentos."),
        (r"not authorized.*|.*is prohibited", MSG_NO_PERMITIDA),
        (r"interrupted", MSG_TIEMPO),
        (r"no tables specified", "Falta la cláusula FROM con la tabla que quieres consultar."),
    ]
    for patron, plantilla in reglas:
        m = re.search(patron, t, re.IGNORECASE)
        if m:
            return plantilla.format(*m.groups())
    return "La consulta no se pudo ejecutar. Revisa su sintaxis."


# ---------- Conexión ----------
def _autorizador(accion, arg1, arg2, _db, _origen):
    """Solo lectura: permite SELECT, lecturas y funciones; todo lo demás se deniega."""
    if accion == sqlite3.SQLITE_FUNCTION:
        nombre = (arg2 or "").lower()
        if nombre in _FUNCIONES_BLOQUEADAS or nombre.startswith("pragma_"):
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
    if accion == sqlite3.SQLITE_READ:
        return sqlite3.SQLITE_DENY if (arg1 or "").lower().startswith("sqlite_") else sqlite3.SQLITE_OK
    if accion in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def _valor_json(v):
    if isinstance(v, bytes):
        return f"<binario {len(v)} bytes>"
    if isinstance(v, str) and len(v) > MAX_CARACTERES_CELDA:
        return v[:MAX_CARACTERES_CELDA] + "…"
    return v


def _norm(v):
    return round(v, 6) if isinstance(v, float) else v


def _filas_norm(filas) -> list[tuple]:
    return [tuple(_norm(v) for v in f) for f in filas]


def _diferencia(esp_cols: int, esp_filas, obt_cols: int, obt_filas, ordenado: bool, truncado: bool) -> str | None:
    if esp_cols != obt_cols:
        return "columnas"
    if truncado or len(esp_filas) != len(obt_filas):
        return "filas_cantidad"
    a, b = _filas_norm(esp_filas), _filas_norm(obt_filas)
    if Counter(a) != Counter(b):
        return "contenido"
    if ordenado and a != b:
        return "orden"
    return None


def evaluar_consulta(
    setup_sql: str,
    solucion_sql: str,
    consulta: str,
    *,
    tiempo_max_seg: float | None = None,
    max_filas: int | None = None,
) -> ResultadoSandbox:
    """Ejecuta la consulta del estudiante en un SQLite en memoria y la compara con la solución.

    Lanza ErrorConfiguracionDesafio si el setup o la solución de referencia fallan.
    """
    tiempo_max = tiempo_max_seg or settings.sandbox_tiempo_max_seg
    tope = max_filas or settings.sandbox_max_filas
    sql = (consulta or "").strip()
    if not sql:
        return ResultadoSandbox(False, "vacia", MSG_VACIA)
    if primera_palabra(sql) not in ("select", "with"):
        return ResultadoSandbox(False, "no_permitida", MSG_NO_PERMITIDA)

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        # --- Parte de confianza: setup y solución ---
        try:
            conn.executescript(setup_sql)
            cur = conn.execute(solucion_sql)
            esperado = cur.fetchall()
            esp_cols = len(cur.description or [])
            conn.execute("PRAGMA query_only = ON")
        except sqlite3.Error as e:
            raise ErrorConfiguracionDesafio(f"Setup o solución inválidos: {e}") from e

        # --- Parte del estudiante: restringida ---
        if hasattr(conn, "enable_load_extension"):
            conn.enable_load_extension(False)
        if hasattr(conn, "setlimit"):
            conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, LIMITE_LONGITUD_VALOR)
            conn.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 10_000)
            conn.setlimit(sqlite3.SQLITE_LIMIT_EXPR_DEPTH, 100)
        conn.set_authorizer(_autorizador)
        limite = time.monotonic() + tiempo_max
        agotado = [False]

        def _progreso():
            if time.monotonic() > limite:
                agotado[0] = True
                return 1
            return 0

        conn.set_progress_handler(_progreso, 1000)
        try:
            cur = conn.execute(sql)
            filas = cur.fetchmany(tope + 1)
            columnas = [d[0] for d in (cur.description or [])]
        except (sqlite3.ProgrammingError, sqlite3.Warning) as e:
            if "one statement" in str(e).lower():
                return ResultadoSandbox(False, "varias_sentencias", MSG_VARIAS, str(e))
            return ResultadoSandbox(False, "error_sql", _traducir_error(str(e)), str(e))
        except sqlite3.Error as e:
            detalle = str(e)
            if agotado[0]:
                return ResultadoSandbox(False, "tiempo_agotado", MSG_TIEMPO, detalle)
            if "not authorized" in detalle.lower() or "prohibited" in detalle.lower():
                return ResultadoSandbox(False, "no_permitida", MSG_NO_PERMITIDA, detalle)
            return ResultadoSandbox(False, "error_sql", _traducir_error(detalle), detalle)
        finally:
            conn.set_progress_handler(None, 0)
    finally:
        conn.close()

    truncado = len(filas) > tope
    filas = filas[:tope]
    mostradas = [[_valor_json(v) for v in f] for f in filas]
    ordenado = tiene_order_by_superior(solucion_sql)
    dif = _diferencia(esp_cols, esperado, len(columnas), filas, ordenado, truncado)
    if dif is None:
        return ResultadoSandbox(True, "correcto", MSG_CORRECTO, None, columnas, mostradas, len(filas), False)
    return ResultadoSandbox(
        False, "resultado_distinto", MSG_DISTINTO[dif], None, columnas, mostradas, len(filas), truncado
    )
