import { cliente } from "./cliente";

export interface Notificacion {
  id: number;
  tipo: string;
  texto: string;
  regla: string | null;
  concepto_id: number | null;
  leida: boolean;
  creada_en: string;
  ajuste_id: number | null;
}

export interface ListaNotificaciones {
  notificaciones: Notificacion[];
  no_leidas: number;
}

export const EVENTO_NOTIFICACIONES_ACTUALIZADAS = "notificaciones:actualizar";

export const avisarNotificacionesActualizadas = () =>
  window.dispatchEvent(new Event(EVENTO_NOTIFICACIONES_ACTUALIZADAS));

export const listarNotificaciones = () =>
  cliente.get<ListaNotificaciones>("/notificaciones").then((r) => r.data);

export const marcarNotificacionLeida = (id: number) =>
  cliente.post<{ ok: boolean; id: number }>(`/notificaciones/${id}/leida`).then((r) => r.data);

export const marcarTodasNotificacionesLeidas = () =>
  cliente.post<{ ok: boolean; actualizadas: number }>("/notificaciones/leer-todas").then((r) => r.data);
