import type { AjusteNivel, Dificultad, EstadoDesafio, MensajeMotor } from "../../api/tiposDesafios";

export function formatearDuracion(segundos: number): string {
  const s = Math.max(0, Math.round(segundos));
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  const resto = s % 60;
  return resto === 0 ? `${m} min` : `${m} min ${resto} s`;
}

export const ETIQUETA_DIFICULTAD: Record<Dificultad, string> = {
  D1: "D1 · Básica",
  D2: "D2 · Intermedia",
  D3: "D3 · Avanzada",
};

export const ETIQUETA_ESTADO: Record<EstadoDesafio, string> = {
  sin_iniciar: "Sin iniciar",
  en_curso: "● En curso",
  resuelto: "✓ Resuelto",
};

export const ESTILO_ESTADO: Record<EstadoDesafio, string> = {
  sin_iniciar: "bg-slate-100 text-slate-700",
  en_curso: "bg-amber-100 text-amber-900",
  resuelto: "bg-green-100 text-green-900",
};

export function textoAjusteNivel(a: AjusteNivel): string {
  return `Tu nivel de ayuda en ${a.concepto} pasó de ${a.ns_anterior} a ${a.ns_nuevo}.`;
}

/** R6: el aviso de estancamiento del motor, si lo hay. */
export function mensajeEstancamiento(mensajes: MensajeMotor[] | undefined): MensajeMotor | undefined {
  return mensajes?.find((m) => m.tipo === "estancamiento");
}
