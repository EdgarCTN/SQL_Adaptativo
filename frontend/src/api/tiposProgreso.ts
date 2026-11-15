export interface NivelConcepto {
  codigo: string;
  nombre: string;
  ns: number;
  desafios_resueltos: number;
}

export interface CambioNivel {
  concepto: string;
  ns_anterior: number;
  ns_nuevo: number;
  texto: string;
  fecha: string;
}

export interface AyudasUsadas {
  AY1: number;
  AY2: number;
  AY3: number;
  AY4: number;
  total: number;
}

export interface ResumenProgreso {
  sin_actividad: boolean;
  sugerencia: string | null;
  desafios_resueltos: number;
  desafios_disponibles: number;
  sesiones_abandonadas: number;
  diagnostico_completado: boolean;
  niveles: NivelConcepto[];
  ayudas: AyudasUsadas;
  cambios_recientes: CambioNivel[];
}

export interface OpcionDesafio {
  id: number;
  titulo: string;
}

export interface IntentoHistorial {
  id: number;
  sesion_id: number;
  desafio_id: number;
  desafio: string;
  concepto: string;
  dificultad: "D1" | "D2" | "D3";
  numero: number;
  correcto: boolean;
  resultado: string;
  estado_sesion: "en_curso" | "resuelto" | "abandonado" | "omitido";
  fecha: string;
}

export interface ListaIntentos {
  intentos: IntentoHistorial[];
  total: number;
  pagina: number;
  tam: number;
  paginas: number;
  desafios: OpcionDesafio[];
}

export interface FiltrosIntentos {
  desafioId?: number;
  desde?: string; // fecha y hora ISO
  hasta?: string;
  pagina: number;
  tam: number;
}

export interface OpcionConcepto {
  codigo: string;
  nombre: string;
}

export interface PuntoIndicadores {
  sesion_id: number;
  concepto: string;
  concepto_nombre: string;
  fecha: string;
  ta: number | null;
  ni: number | null;
  tr: number | null;
  ua: number | null;
  n_ventana: number;
  ns: number;
}

export interface CambioNs {
  concepto: string;
  concepto_nombre: string;
  fecha: string;
  ns_anterior: number;
  ns_nuevo: number;
  texto: string;
}

export interface Evolucion {
  concepto: string | null;
  indicadores: PuntoIndicadores[];
  cambios_ns: CambioNs[];
  conceptos_con_datos: OpcionConcepto[];
}

export interface FiltrosEvolucion {
  concepto?: string;
  desde?: string;
  hasta?: string;
}
