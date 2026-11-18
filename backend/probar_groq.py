import logging
logging.basicConfig(level=logging.WARNING, format="%(name)s: %(message)s")

from app.core.config import settings
from app.modules.asistencia import validador
from app.modules.asistencia.llm.fabrica import obtener_proveedor
from app.modules.asistencia.llm.base import SolicitudLLM

print("Proveedor:", settings.llm_provider, "| modelo:", settings.groq_model)
print("Clave cargada:", bool(settings.groq_api_key.strip()))

prov = obtener_proveedor()
sol = SolicitudLLM(
    tipo_ayuda="AY1",
    prompt_sistema=(
        "Eres un tutor de SQL. Responde SOLO con un JSON con tipo_entregado, "
        "mensaje y codigo_sql. Da una pista breve en español, sin dar la solución."
    ),
    mensaje_usuario="El estudiante escribió SELECT * FROM libros WHERE y no sabe cómo filtrar por año.",
    ayuda_respaldo={"mensaje": "Revisa qué condición necesita cada fila para aparecer en el resultado.", "codigo_sql": None},
)
r = prov.generar(sol)

print("\nProveedor que respondió:", r.proveedor)
print("¿Es respaldo (mock)?   :", r.es_respaldo)
print("Etiquetas:", r.etiquetas)
print("Texto:", r.texto)

v = validador.validar(r.texto, "AY1")
print("\nValidador ok:", v.ok, "| motivo:", getattr(v, "motivo", None))
