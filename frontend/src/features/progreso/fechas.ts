/** Las fechas del filtro son días del calendario del estudiante (`AAAA-MM-DD`); al API viajan como instantes ISO. */
export function inicioDelDia(dia: string): string | undefined {
  if (!dia) return undefined;
  const f = new Date(`${dia}T00:00:00`);
  return Number.isNaN(f.getTime()) ? undefined : f.toISOString();
}

export function finDelDia(dia: string): string | undefined {
  if (!dia) return undefined;
  const f = new Date(`${dia}T23:59:59.999`);
  return Number.isNaN(f.getTime()) ? undefined : f.toISOString();
}

export const MSG_RANGO_INVERTIDO = "La fecha de inicio no puede ser posterior a la fecha de fin.";

export function rangoInvertido(desde: string, hasta: string): boolean {
  return Boolean(desde) && Boolean(hasta) && desde > hasta;
}

export function formatearFechaHora(iso: string): string {
  const f = new Date(iso);
  return Number.isNaN(f.getTime())
    ? ""
    : f.toLocaleString("es", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function formatearFechaCorta(iso: string): string {
  const f = new Date(iso);
  return Number.isNaN(f.getTime()) ? "" : f.toLocaleDateString("es", { day: "2-digit", month: "short", year: "numeric" });
}

export function formatearNumero(valor: number | null | undefined, decimales = 2): string {
  return valor === null || valor === undefined
    ? "—"
    : valor.toLocaleString("es", { minimumFractionDigits: 0, maximumFractionDigits: decimales });
}

export function formatearPorcentaje(valor: number | null | undefined): string {
  return valor === null || valor === undefined ? "—" : `${Math.round(valor * 100)} %`;
}
