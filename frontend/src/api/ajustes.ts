import { cliente } from "./cliente";
import { avisarNotificacionesActualizadas } from "./notificaciones";
import type { AjusteNivel, ConceptoResumen } from "./tiposDesafios";

export interface AjustePendiente {
  id: number;
  concepto: ConceptoResumen;
  modo: "aviso_previo" | "preguntar";
  texto: string;
  creado_en: string;
}

export interface RespuestaAjuste {
  estado: "aplicado" | "mantenido" | "caducado";
  mensaje: string;
  ajuste_nivel: AjusteNivel | null;
}

export const listarAjustesPendientes = () =>
  cliente.get<{ ajustes: AjustePendiente[] }>("/ajustes/pendientes").then((r) => r.data.ajustes);

export const responderAjuste = (id: number, accion: "aceptar" | "mantener") =>
  cliente.post<RespuestaAjuste>(`/ajustes/${id}/responder`, { accion }).then((r) => {
    avisarNotificacionesActualizadas();
    return r.data;
  });
