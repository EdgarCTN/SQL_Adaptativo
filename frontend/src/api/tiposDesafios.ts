export type Dificultad = "D1" | "D2" | "D3";
export type EstadoDesafio = "sin_iniciar" | "en_curso" | "resuelto";

export interface ConceptoResumen {
  codigo: string;
  nombre: string;
}

export interface DesafioResumen {
  id: number;
  titulo: string;
  concepto: ConceptoResumen;
  dificultad: Dificultad;
  tiempo_referencia_seg: number;
  estado: EstadoDesafio;
}

export interface GrupoDesafios {
  dificultad: Dificultad;
  desafios: DesafioResumen[];
}

export interface ListaDesafios {
  total: number;
  mensaje: string | null;
  conceptos: ConceptoResumen[];
  grupos: GrupoDesafios[];
}

export interface SesionResumen {
  sesion_id: number;
  inicio: string;
  intentos_realizados: number;
}

export interface DesafioDetalle {
  id: number;
  titulo: string;
  enunciado: string;
  recursos: string[];
  concepto: ConceptoResumen;
  dificultad: Dificultad;
  esquema_sql: string;
  tiempo_referencia_seg: number;
  estado: EstadoDesafio;
  sesion_en_curso: SesionResumen | null;
}

export interface InicioSesion {
  sesion_id: number;
  desafio_id: number;
  estado: string;
  inicio: string;
  reanudada: boolean;
  intentos_realizados: number;
}

export type TipoResultado =
  | "correcto"
  | "resultado_distinto"
  | "error_sql"
  | "no_permitida"
  | "varias_sentencias"
  | "tiempo_agotado";

export type CeldaResultado = string | number | boolean | null;

export interface ResultadoIntento {
  numero: number;
  correcto: boolean;
  tipo_resultado: TipoResultado;
  mensaje: string;
  detalle_tecnico: string | null;
  columnas: string[];
  filas: CeldaResultado[][];
  total_filas: number;
  truncado: boolean;
  desafio_resuelto: boolean;
  estado_sesion: string;
  resultado_cierre: string | null;
  tiempo_activo_seg: number | null;
  creado_en: string;
}

export interface ResultadoAbandono {
  estado: string;
  resultado_cierre: string;
  tiempo_activo_seg: number;
  mensaje: string;
}

export type TipoAyuda = "AY1" | "AY2" | "AY3" | "AY4";

export interface RespuestaAyuda {
  solicitud_id: number | null;
  tipo_ayuda: TipoAyuda | null;
  mensaje: string | null;
  codigo_sql: string | null;
  etiquetas: string[];
  fue_respaldo: boolean;
  reformulada: boolean;
  sugerencia: string | null;
  aviso: string | null;
  desafio_marcado_nr: boolean;
}

export interface RespuestaValoracion {
  ok: boolean;
  valor: number;
}

/** Ayuda ya entregada, tal como se muestra en el panel (y se guarda en sessionStorage durante la sesión). */
export interface AyudaRecibida {
  solicitud_id: number;
  tipo_ayuda: TipoAyuda;
  mensaje: string;
  codigo_sql: string | null;
  etiquetas: string[];
  reformulada: boolean;
  sugerencia: string | null;
  aviso: string | null;
  valoracion: 1 | -1 | null;
}
