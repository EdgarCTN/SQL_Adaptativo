/** Un grupo con menos de `n_minimo` estudiantes llega con `suprimido: true` y todas sus cifras en null. */
export interface Suprimible {
  suprimido: boolean;
}

export interface FilaUso extends Suprimible {
  semana: string;
  estudiantes_activos: number | null;
  sesiones: number | null;
  intentos: number | null;
}

export interface FilaDesempeno extends Suprimible {
  concepto: string;
  dificultad: string;
  n_estudiantes: number | null;
  n_desafios: number | null;
  tasa_sa: number | null;
  tasa_cp: number | null;
  tasa_ce: number | null;
  tasa_nr: number | null;
  intentos_medios: number | null;
  tr_mediana: number | null;
}

export interface FilaDistribucionNs extends Suprimible {
  concepto: string;
  n_estudiantes: number | null;
  ns0: number | null;
  ns1: number | null;
  ns2: number | null;
  ns3: number | null;
}

export interface FilaAyuda extends Suprimible {
  tipo: "AY1" | "AY2" | "AY3" | "AY4";
  n_solicitudes: number | null;
  n_estudiantes: number | null;
  n_mostradas_solas: number | null;
  n_valoradas: number | null;
  utiles: number | null;
  no_utiles: number | null;
  proporcion_util: number | null;
}

export interface FilaCambio extends Suprimible {
  concepto: string;
  tipo: "retiro" | "refuerzo" | "recaida" | "otro";
  n_cambios: number | null;
  n_estudiantes: number | null;
  reglas: Record<string, number> | null;
}

export interface LineaBaseReporte extends Suprimible {
  n_estudiantes: number | null;
  m_global_media: number | null;
  por_concepto: (Suprimible & { concepto: string; m_media: number | null })[];
}

export interface ResumenNumerico extends Suprimible {
  n_conceptos: number | null;
  n_estudiantes: number | null;
  media: number | null;
  mediana: number | null;
  minimo: number | null;
  maximo: number | null;
}

export interface Eficacia {
  ns0_sin_recaida: Suprimible & { n_conceptos: number | null; n_estudiantes: number | null; sin_recaida: number | null; proporcion: number | null };
  desafios_hasta_primer_retiro: { global: ResumenNumerico; por_concepto: (ResumenNumerico & { concepto: string })[] };
  sa_por_bloque: (Suprimible & { desde_orden: number; hasta_orden: number; n_estudiantes: number | null; n_desafios: number | null; proporcion_sa: number | null })[];
  activacion_r9_r10: (Suprimible & { regla: "R9" | "R10"; n_activaciones: number | null; n_estudiantes: number | null; n_sesiones: number | null; proporcion_sesiones: number | null })[];
  precision_ns_inicial: Suprimible & {
    n_conceptos: number | null;
    n_estudiantes: number | null;
    coincide: number | null;
    inicial_alto: number | null;
    inicial_bajo: number | null;
    proporcion_coincide: number | null;
  };
}

export interface Reporte {
  periodo: { desde: string | null; hasta: string | null };
  generado_en: string;
  n_minimo: number;
  nota_privacidad: string;
  conceptos: { codigo: string; nombre: string }[];
  resumen: Suprimible & { estudiantes_activos: number | null };
  uso: FilaUso[];
  desempeno: FilaDesempeno[];
  distribucion_ns: FilaDistribucionNs[];
  ayudas: FilaAyuda[];
  retiros_refuerzos: FilaCambio[];
  linea_base: LineaBaseReporte;
  eficacia: Eficacia;
}

export type TipoExportacion = "intentos" | "ayudas" | "cambios_ns" | "indicadores" | "todos";
export interface FiltrosReporte {
  desde?: string;
  hasta?: string;
}
