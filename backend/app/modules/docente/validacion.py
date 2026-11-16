"""Validación automática de un desafío antes de guardarlo (entrega 12).

Cada problema es {"campo", "mensaje"}. Los campos anidados usan puntos:
`errores_tipicos.0.ejemplo`, `ayudas_respaldo.AY3.codigo_sql`.
Reutiliza el sandbox y los validadores V3 (AY1), V4 (AY2) y V5 (AY3) de la ayuda, de modo que lo que el banco acepta
es lo mismo que el sistema exige en tiempo de ejecución.
"""
import re
import sqlite3
import time

from app.modules.asistencia.validador import (
    ContextoValidacion,
    v3_pista_sin_codigo,
    v4_ejemplo_otro_contexto,
    v5_esqueleto_incompleto,
)
from app.modules.desafios.sandbox import ErrorConfiguracionDesafio, evaluar_consulta, primera_palabra

N_ERRORES_TIPICOS = 3
TIPOS_AYUDA = ("AY1", "AY2", "AY3", "AY4")
TIEMPO_MAX_PRUEBA_SEG = 5.0  # tope para ejecutar el setup y la solución (de confianza, pero sin ciclos infinitos)
MSG_OBLIGATORIO = "Este campo es obligatorio."
MSG_SOLO_LECTURA = "Debe ser una consulta de lectura: SELECT, o WITH seguido de SELECT."

_ACCIONES_PROHIBIDAS = {sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_PRAGMA}
_FUNCIONES_PROHIBIDAS = {"load_extension", "readfile", "writefile", "edit"}


def problema(campo: str, mensaje: str) -> dict:
    return {"campo": campo, "mensaje": mensaje}


def _autorizador(accion, arg1, arg2, _db, _origen):
    """El setup lo escribe un docente, pero nunca debe tocar archivos del servidor (ATTACH, PRAGMA, funciones de archivo)."""
    if accion in _ACCIONES_PROHIBIDAS:
        return sqlite3.SQLITE_DENY
    if accion == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in _FUNCIONES_PROHIBIDAS:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _mensaje_sqlite(e: Exception) -> str:
    texto = str(e)
    bajo = texto.lower()
    if "interrupted" in bajo:
        return f"tardó más de {TIEMPO_MAX_PRUEBA_SEG:g} s en ejecutarse (revisa ciclos o combinaciones innecesarias)."
    if "not authorized" in bajo or "prohibited" in bajo:
        return "usa una operación no permitida (ATTACH, DETACH, PRAGMA o funciones de archivo)."
    if "one statement" in bajo:
        return "debe ser una sola sentencia."
    return texto


def _probar_base(setup: str, solucion: str) -> tuple[str | None, str | None]:
    """Ejecuta el setup y luego la solución en un SQLite en memoria con límites. Devuelve (error_setup, error_solucion)."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    try:
        conn.set_authorizer(_autorizador)

        def _con_limite():
            limite = time.monotonic() + TIEMPO_MAX_PRUEBA_SEG
            conn.set_progress_handler(lambda: 1 if time.monotonic() > limite else 0, 1000)

        _con_limite()
        try:
            conn.executescript(setup)
        except sqlite3.Error as e:
            return _mensaje_sqlite(e), None
        _con_limite()
        try:
            conn.execute(solucion).fetchmany(1000)
        except sqlite3.Error as e:
            return None, _mensaje_sqlite(e)
        return None, None
    finally:
        conn.close()


def _limpiar_prefijo(msg: str) -> str:
    texto = re.sub(r"^V\d:\s*", "", msg or "").strip()
    return texto[:1].upper() + texto[1:]


def _validador(fn, tipo: str, mensaje: str, codigo: str, solucion: str, esquema: str, setup: str) -> str | None:
    ctx = ContextoValidacion(
        texto="",
        tipo_pedido=tipo,
        datos={"tipo_entregado": tipo, "mensaje": mensaje, "codigo_sql": codigo or None},
        solucion=solucion,
        esquema=esquema,
        setup=setup,
    )
    try:
        motivo = fn(ctx)
    except Exception:  # noqa: BLE001 - un SQL que no se puede analizar es un problema del campo, no un 500
        return "No se pudo analizar el código SQL; revisa que esté bien escrito."
    return _limpiar_prefijo(motivo) if motivo else None


def _evaluar(setup: str, solucion: str, consulta: str):
    try:
        return evaluar_consulta(setup, solucion, consulta)
    except ErrorConfiguracionDesafio:  # no debería ocurrir: el setup y la solución ya se probaron
        return None


def validar_contenido(d: dict) -> list[dict]:
    """`d` ya viene normalizado (textos recortados). No consulta la base de datos."""
    p: list[dict] = []
    for campo in ("titulo", "enunciado", "esquema_sql", "sandbox_setup_sql", "solucion_referencia"):
        if not d.get(campo):
            p.append(problema(campo, MSG_OBLIGATORIO))
    if d.get("dificultad") not in ("D1", "D2", "D3"):
        p.append(problema("dificultad", "Elige una dificultad: D1, D2 o D3."))

    setup, solucion, esquema = d.get("sandbox_setup_sql", ""), d.get("solucion_referencia", ""), d.get("esquema_sql", "")
    base_ok = False
    if setup and solucion:
        if primera_palabra(solucion) not in ("select", "with"):
            p.append(problema("solucion_referencia", MSG_SOLO_LECTURA))
        else:
            e_setup, e_solucion = _probar_base(setup, solucion)
            if e_setup:
                p.append(problema("sandbox_setup_sql", f"El setup no se pudo ejecutar: {e_setup}"))
            elif e_solucion:
                p.append(problema("solucion_referencia", f"La solución no se pudo ejecutar con el setup: {e_solucion}"))
            else:
                r = _evaluar(setup, solucion, solucion)
                if r is not None and r.correcto:
                    base_ok = True
                else:
                    detalle = r.mensaje if r is not None else "no se pudo evaluar"
                    p.append(problema("solucion_referencia", f"La solución no se acepta a sí misma: {detalle}"))

    # --- 3 errores típicos que deben fallar ---
    errores = d.get("errores_tipicos") or []
    if len(errores) != N_ERRORES_TIPICOS:
        p.append(problema("errores_tipicos", f"Indica exactamente {N_ERRORES_TIPICOS} errores típicos (hay {len(errores)})."))
    for i, e in enumerate(errores):
        if not e.get("descripcion"):
            p.append(problema(f"errores_tipicos.{i}.descripcion", MSG_OBLIGATORIO))
        ejemplo = e.get("ejemplo", "")
        if not ejemplo:
            p.append(problema(f"errores_tipicos.{i}.ejemplo", MSG_OBLIGATORIO))
        elif base_ok:
            r = _evaluar(setup, solucion, ejemplo)
            if r is None:
                continue
            if r.correcto:
                p.append(problema(f"errores_tipicos.{i}.ejemplo", "Este ejemplo devuelve el resultado correcto, así que no es un error típico."))
            elif r.tipo in ("no_permitida", "varias_sentencias"):
                p.append(problema(f"errores_tipicos.{i}.ejemplo", "El ejemplo debe ser una sola consulta de lectura (SELECT, o WITH seguido de SELECT)."))

    # --- 4 ayudas de respaldo ---
    ayudas = d.get("ayudas_respaldo") or {}
    for tipo in TIPOS_AYUDA:
        a = ayudas.get(tipo) or {}
        mensaje, codigo = a.get("mensaje", ""), a.get("codigo_sql") or ""
        if not mensaje:
            p.append(problema(f"ayudas_respaldo.{tipo}.mensaje", MSG_OBLIGATORIO))
        campo_codigo = f"ayudas_respaldo.{tipo}.codigo_sql"
        if tipo == "AY1":
            if codigo:
                p.append(problema(campo_codigo, "AY1 orienta sin código: deja este campo vacío."))
            elif mensaje:
                motivo = _validador(v3_pista_sin_codigo, tipo, mensaje, codigo, solucion, esquema, setup)
                if motivo:
                    p.append(problema(f"ayudas_respaldo.{tipo}.mensaje", motivo))
        elif tipo in ("AY2", "AY3"):
            if not codigo:
                p.append(problema(campo_codigo, MSG_OBLIGATORIO))
                continue
            fn = v4_ejemplo_otro_contexto if tipo == "AY2" else v5_esqueleto_incompleto
            motivo = _validador(fn, tipo, mensaje, codigo, solucion, esquema, setup)
            if motivo:
                p.append(problema(campo_codigo, motivo))
        else:  # AY4: la solución completa debe ser correcta
            if not codigo:
                p.append(problema(campo_codigo, MSG_OBLIGATORIO))
            elif base_ok:
                r = _evaluar(setup, solucion, codigo)
                if r is not None and not r.correcto:
                    p.append(problema(campo_codigo, "AY4 debe ser una solución correcta del desafío; con este código el sandbox no la acepta."))
    return p
