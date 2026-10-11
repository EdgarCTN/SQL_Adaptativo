// Borrador del diagnóstico en sessionStorage: sobrevive a una recarga y se borra al guardar.

export interface RespuestaLocal {
  opciones: string[];
  confianza: number | null;
  omitir: string | null;
}
export type Respuestas = Record<string, RespuestaLocal>;

export interface Borrador {
  cuestionarioId: number;
  paso: number;
  respuestas: Respuestas;
}

const clave = (usuarioId: number) => `diagnostico:borrador:${usuarioId}`;

function limpiarRespuestas(crudo: unknown): Respuestas {
  const salida: Respuestas = {};
  if (!crudo || typeof crudo !== "object") return salida;
  for (const [id, valor] of Object.entries(crudo as Record<string, unknown>)) {
    if (!valor || typeof valor !== "object") continue;
    const v = valor as Record<string, unknown>;
    const opciones = Array.isArray(v.opciones) ? v.opciones.filter((o): o is string => typeof o === "string") : [];
    const confianza =
      typeof v.confianza === "number" && Number.isInteger(v.confianza) && v.confianza >= 1 && v.confianza <= 5
        ? v.confianza
        : null;
    const omitir = typeof v.omitir === "string" ? v.omitir : null;
    salida[id] = { opciones, confianza, omitir };
  }
  return salida;
}

export function leerBorrador(usuarioId: number, cuestionarioId: number): Borrador | null {
  try {
    const texto = sessionStorage.getItem(clave(usuarioId));
    if (!texto) return null;
    const dato = JSON.parse(texto) as Record<string, unknown>;
    if (dato.cuestionarioId !== cuestionarioId) return null; // otra versión del cuestionario
    const paso = typeof dato.paso === "number" && Number.isInteger(dato.paso) && dato.paso >= 0 ? dato.paso : 0;
    return { cuestionarioId, paso, respuestas: limpiarRespuestas(dato.respuestas) };
  } catch {
    return null;
  }
}

export function guardarBorrador(usuarioId: number, borrador: Borrador): void {
  try {
    sessionStorage.setItem(clave(usuarioId), JSON.stringify(borrador));
  } catch {
    /* sin almacenamiento: el borrador solo vive mientras la pantalla siga abierta */
  }
}

export function borrarBorrador(usuarioId: number): void {
  try {
    sessionStorage.removeItem(clave(usuarioId));
  } catch {
    /* nada que borrar */
  }
}
