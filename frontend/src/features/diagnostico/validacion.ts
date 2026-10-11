import type { Cuestionario, Parte, Pregunta, RespuestaEnvio } from "../../api/tiposLineaBase";
import type { RespuestaLocal, Respuestas } from "./borrador";

export const esPrueba = (p: Pregunta): boolean => !p.tipo; // Parte 2

export const respuestaVacia = (): RespuestaLocal => ({ opciones: [], confianza: null, omitir: null });

export function estaRespondida(p: Pregunta, r: RespuestaLocal | undefined): boolean {
  if (!r) return false;
  const existe = (id: string) => p.opciones.some((o) => o.id === id);
  if (esPrueba(p)) {
    if (r.omitir) return true;
    if (r.opciones.length !== 1 || !existe(r.opciones[0])) return false;
    const opcion = p.opciones.find((o) => o.id === r.opciones[0]);
    if (opcion?.es_no_se) return true; // «No sé» no pide confianza
    return r.confianza !== null && r.confianza >= 1 && r.confianza <= 5;
  }
  if (p.tipo === "unica") return r.opciones.length === 1 && existe(r.opciones[0]);
  return r.opciones.length >= 1 && r.opciones.every(existe);
}

const esObligatoria = (p: Pregunta) => p.obligatoria !== false;

export function pendientesDeParte(parte: Parte, respuestas: Respuestas): string[] {
  return parte.preguntas.filter((p) => esObligatoria(p) && !estaRespondida(p, respuestas[p.id])).map((p) => p.id);
}

export function contarPreguntas(partes: Parte[]): number {
  return partes.reduce((n, parte) => n + parte.preguntas.length, 0);
}

export function contarRespondidas(partes: Parte[], respuestas: Respuestas): number {
  return partes.reduce((n, parte) => n + parte.preguntas.filter((p) => estaRespondida(p, respuestas[p.id])).length, 0);
}

export function construirEnvio(cuestionario: Cuestionario, respuestas: Respuestas) {
  const lista: RespuestaEnvio[] = [];
  for (const parte of cuestionario.partes) {
    for (const p of parte.preguntas) {
      const r = respuestas[p.id];
      if (!estaRespondida(p, r) || !r) continue;
      if (esPrueba(p)) {
        if (r.omitir) {
          lista.push({ pregunta_id: p.id, omitir: r.omitir });
        } else if (p.opciones.find((o) => o.id === r.opciones[0])?.es_no_se) {
          lista.push({ pregunta_id: p.id, opciones: [...r.opciones] });
        } else {
          lista.push({ pregunta_id: p.id, opciones: [...r.opciones], confianza: r.confianza ?? undefined });
        }
      } else {
        lista.push({ pregunta_id: p.id, opciones: [...r.opciones] });
      }
    }
  }
  return { cuestionario_id: cuestionario.id, respuestas: lista };
}
