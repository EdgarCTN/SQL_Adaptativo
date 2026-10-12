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
