"""Minimiza los textos libres antes de enviarlos al proveedor de lenguaje."""
import re


def anonimizar(texto: str, personales: tuple[str, ...] = ()) -> str:
    texto = re.sub(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", "[correo omitido]", texto or "", flags=re.I)
    for dato in sorted(set(personales), key=len, reverse=True):
        if dato.strip():
            texto = re.sub(r"(?<!\w)" + re.escape(dato.strip()) + r"(?!\w)", "[dato omitido]", texto, flags=re.I)
    return re.sub(
        r"\b(?:ns_actual|nivel[ _]+(?:de[ _]+)?soporte|NS|TA|NI|TR|UA)\s*[:=]\s*[-+]?\d+(?:[.,]\d+)?",
        "[indicador omitido]", texto, flags=re.I,
    )
