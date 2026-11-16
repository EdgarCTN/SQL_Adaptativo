import type { ConceptoResumen, Dificultad } from "./tiposDesafios";

export type TipoAyuda = "AY1" | "AY2" | "AY3" | "AY4";
export const TIPOS_AYUDA: TipoAyuda[] = ["AY1", "AY2", "AY3", "AY4"];

export interface ErrorTipico {
  descripcion: string;
  ejemplo: string;
}

export interface AyudaRespaldo {
  mensaje: string;
  codigo_sql: string | null;
}

export interface DesafioFila {
  id: number;
  titulo: string;
  concepto: ConceptoResumen;
  dificultad: Dificultad;
  tiempo_referencia_seg: number;
  activo: boolean;
  n_sesiones: number;
  creado_en: string | null;
}

export interface ListaDocente {
  total: number;
  desafios: DesafioFila[];
}

/** Solo lo reciben docente y administrador: incluye lo que el estudiante nunca ve. */
export interface DesafioDocente extends DesafioFila {
  enunciado: string;
  recursos: string[];
  esquema_sql: string;
  sandbox_setup_sql: string;
  solucion_referencia: string;
  errores_tipicos: ErrorTipico[];
  ayudas_respaldo: Record<TipoAyuda, AyudaRespaldo>;
}

export interface OpcionesDocente {
  conceptos: ConceptoResumen[];
  dificultades: Dificultad[];
  tiempos_referencia: Record<string, number>;
  n_errores_tipicos: number;
}

export interface Problema {
  campo: string;
  mensaje: string;
}

export interface Validacion {
  valido: boolean;
  problemas: Problema[];
}

export interface FiltrosDocente {
  concepto?: string;
  dificultad?: string;
  estado?: string;
  q?: string;
}

/** Lo que el formulario edita (todo texto; recursos uno por línea). */
export interface BorradorDesafio {
  titulo: string;
  enunciado: string;
  recursos: string;
  concepto: string;
  dificultad: Dificultad | "";
  esquema_sql: string;
  sandbox_setup_sql: string;
  solucion_referencia: string;
  errores_tipicos: ErrorTipico[];
  ayudas_respaldo: Record<TipoAyuda, { mensaje: string; codigo_sql: string }>;
  tiempo_referencia_seg: string;
}

/** Cuerpo que recibe la API (DesafioIn). */
export interface CuerpoDesafio {
  titulo: string;
  enunciado: string;
  recursos: string[];
  concepto: string;
  dificultad: string;
  esquema_sql: string;
  sandbox_setup_sql: string;
  solucion_referencia: string;
  errores_tipicos: ErrorTipico[];
  ayudas_respaldo: Record<TipoAyuda, { mensaje: string; codigo_sql: string | null }>;
  tiempo_referencia_seg: number | null;
}
