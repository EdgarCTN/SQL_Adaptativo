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
  verificacion: boolean; // R7: es el desafío de verificación pendiente
}

export interface GrupoDesafios {
  dificultad: Dificultad;
  desafios: DesafioResumen[];
  empieza_aqui: boolean; // R0: dificultad inicial del estudiante (no bloquea las demás)
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
  verificacion: boolean; // R7: la ayuda no se ofrece sola y, si la pides, ya no cuenta como «sin ayuda»
}

export interface InicioSesion {
  sesion_id: number;
  desafio_id: number;
  estado: string;
  inicio: string;
  reanudada: boolean;
  intentos_realizados: number;
  ajuste_nivel?: AjusteNivel | null; // R12: el nivel de ayuda subió a 1 al pasar a una dificultad mayor
  mensajes?: MensajeMotor[];
}

export type TipoResultado =
  | "correcto"
  | "resultado_distinto"
  | "error_sql"
  | "no_permitida"
  | "varias_sentencias"
  | "tiempo_agotado";

export type CeldaResultado = string | number | boolean | null;

export interface AjusteNivel {
  concepto: string;
  ns_anterior: number;
  ns_nuevo: number;
  motivo: string; // texto para el estudiante
}

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
  ajuste_nivel: AjusteNivel | null;
  mensajes: MensajeMotor[]; // avisos del motor que no cambian el nivel (R6 estancamiento, R11 tras un acierto)
  reflexion: MensajeMotor | null; // R10: no bloquea la ayuda
  oferta_ayuda: OfertaAyuda | null; // tras un envío fallido, con NS ≥ 1 y según la preferencia 3.3
}

export interface OfertaAyuda {
  modo: "ofrecer" | "mostrar_sola";
  motivo: "fallos" | "tiempo";
  tipo_ayuda: "AY1" | "AY2" | "AY3" | "AY4";
  texto: string; // «¿Quieres una pista?» o el aviso de la ayuda mostrada sola
  boton: string | null;
  boton_rechazo: string | null;
  ayuda: RespuestaAyuda | null; // solo con mostrar_sola: ya entregada
}

export interface ResultadoAbandono {
  estado: string;
  resultado_cierre: string;
  tiempo_activo_seg: number;
  mensaje: string;
  ajuste_nivel: AjusteNivel | null;
  mensajes: MensajeMotor[];
}

export type MotivoOmision = "muy_facil" | "muy_dificil";

export interface DesafioSugerido {
  id: number;
  titulo: string;
  dificultad: Dificultad;
}

export interface VerificacionAsignada {
  concepto: string;
  desafio_id: number;
  titulo: string;
  dificultad: Dificultad;
  mensaje: string;
}

export interface MensajeMotor {
  clave: string;
  tipo:
    | "retiro"
    | "refuerzo"
    | "verificacion"
    | "sugerencia"
    | "estancamiento"
    | "recaida"
    | "cambio_dificultad"
    | "reenganche"
    | "retiro_aviso" // R13: aviso previo, el retiro se aplica en el siguiente desafío salvo que mantengas la ayuda
    | "retiro_pregunta" // R13: el retiro solo se aplica si aceptas
    | "reflexion" // R10: pregunta de reflexión tras 3 envíos fallidos seguidos y rápidos
    | "sobreconfianza"; // R11: explicar o simplificar tras un acierto
  texto: string;
  enlace?: string | null; // ruta del frontend; R6 la usa para llevar a los desafíos del concepto previo
  ajuste_id?: number | null; // R13: retiro pendiente al que se responde en POST /ajustes/{id}/responder
}

export interface ResultadoOmision {
  estado: string;
  motivo: MotivoOmision;
  mensaje: string;
  ajuste_nivel: AjusteNivel | null;
  sugerido: DesafioSugerido | null;
  verificacion: VerificacionAsignada | null;
  mensajes: MensajeMotor[];
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
  mostrada_sola?: boolean; // la plataforma la mostró sin pedirla (preferencia 3.3)
}
