import { cliente } from "./cliente";
import type {
  DesafioDetalle,
  InicioSesion,
  ListaDesafios,
  MotivoOmision,
  ResultadoAbandono,
  ResultadoIntento,
  ResultadoOmision,
} from "./tiposDesafios";
import { avisarNotificacionesActualizadas } from "./notificaciones";

export const listarDesafios = (concepto?: string) =>
  cliente.get<ListaDesafios>("/desafios", { params: concepto ? { concepto } : undefined }).then((r) => r.data);

export const obtenerDesafio = (id: number) => cliente.get<DesafioDetalle>(`/desafios/${id}`).then((r) => r.data);

export const iniciarDesafio = (id: number) =>
  cliente.post<InicioSesion>(`/desafios/${id}/iniciar`).then((r) => {
    if (r.data.mensajes?.length) avisarNotificacionesActualizadas();
    return r.data;
  });

export const enviarIntento = (id: number, codigo: string) =>
  cliente.post<ResultadoIntento>(`/desafios/${id}/intentos`, { codigo }).then((r) => {
    if (r.data.desafio_resuelto || r.data.mensajes.length || r.data.reflexion) avisarNotificacionesActualizadas();
    return r.data;
  });

export const abandonarDesafio = (id: number) =>
  cliente.post<ResultadoAbandono>(`/desafios/${id}/abandonar`).then((r) => {
    avisarNotificacionesActualizadas();
    return r.data;
  });

export const omitirDesafio = (id: number, motivo: MotivoOmision) =>
  cliente.post<ResultadoOmision>(`/desafios/${id}/omitir`, { motivo }).then((r) => {
    avisarNotificacionesActualizadas();
    return r.data;
  });

/** Latido de actividad: el llamador ignora cualquier fallo. */
export const enviarLatido = (id: number) =>
  cliente.post<{ ok: boolean; tiempo_activo_seg: number }>(`/desafios/${id}/latido`).then((r) => r.data);
