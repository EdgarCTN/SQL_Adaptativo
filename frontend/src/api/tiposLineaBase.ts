export interface Opcion {
  id: string;
  texto: string;
  excluyente?: boolean;
  es_no_se?: boolean;
  codigo?: string;
}

export interface Pregunta {
  id: string;
  numero?: number;
  tipo?: "unica" | "multiple"; // las preguntas de la Parte 2 no traen tipo
  obligatoria?: boolean;
  enunciado: string;
  nota?: string;
  opciones: Opcion[];
  nivel?: number;
  dificultad?: string;
  concepto?: string;
  concepto_nombre?: string;
}

export interface TablaEsquema {
  nombre: string;
  columnas: string[];
  filas: string[][];
}

export interface MotivoOmision {
  codigo: string;
  texto: string;
}

export interface Parte {
  id: string;
  titulo: string;
  preguntas: Pregunta[];
  instrucciones?: string[];
  escala_confianza?: Record<string, string>;
  omitir_motivos?: MotivoOmision[];
  esquema?: { tablas: TablaEsquema[] };
}

export interface Cuestionario {
  id: number;
  version: number;
  introduccion: string;
  partes: Parte[];
}

export type SiguientePaso = "consentimiento" | "cuestionario" | "completado" | "no_disponible";

export interface EstadoLineaBase {
  linea_base_completada: boolean;
  consentimiento_aceptado: boolean;
  version_consentimiento: string;
  cuestionario_disponible: boolean;
  cuestionario_id: number | null;
  siguiente_paso: SiguientePaso;
}

export interface ResultadoConsentimiento {
  aceptado: boolean;
  version?: string | null;
  aceptado_en?: string | null;
  mensaje: string;
}

export interface RespuestaEnvio {
  pregunta_id: string;
  opciones?: string[];
  confianza?: number;
  omitir?: string;
}

export interface EnvioRespuestas {
  cuestionario_id: number;
  respuestas: RespuestaEnvio[];
}

export interface VerificacionInicial {
  concepto: string;
  desafio_id: number;
  titulo: string;
  dificultad: "D1" | "D2" | "D3";
  mensaje: string;
}

export interface ResultadoEnvio {
  ok: boolean;
  mensaje: string;
  aviso: string | null;
  linea_base_completada: boolean;
  verificaciones?: VerificacionInicial[];
}
