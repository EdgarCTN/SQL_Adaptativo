const BASE: Record<string, string> = {
  titulo: "Título",
  enunciado: "Enunciado",
  recursos: "Recursos",
  concepto: "Concepto",
  dificultad: "Dificultad",
  esquema_sql: "Esquema",
  sandbox_setup_sql: "Datos de prueba (setup)",
  solucion_referencia: "Solución de referencia",
  tiempo_referencia_seg: "Tiempo de referencia",
  errores_tipicos: "Errores típicos",
};

/** Nombre legible de un campo del servidor (p. ej. `ayudas_respaldo.AY3.codigo_sql` → «Ayuda AY3 · código»). */
export function etiquetaCampo(campo: string): string {
  const e = /^errores_tipicos\.(\d+)\.(descripcion|ejemplo)$/.exec(campo);
  if (e) return `Error típico ${Number(e[1]) + 1} · ${e[2] === "ejemplo" ? "ejemplo" : "descripción"}`;
  const a = /^ayudas_respaldo\.(AY\d)\.(mensaje|codigo_sql)$/.exec(campo);
  if (a) return `Ayuda ${a[1]} · ${a[2] === "mensaje" ? "mensaje" : "código"}`;
  return BASE[campo] ?? campo;
}
