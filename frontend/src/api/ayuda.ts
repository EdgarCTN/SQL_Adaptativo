import { cliente } from "./cliente";
import type { RespuestaAyuda, RespuestaValoracion } from "./tiposDesafios";

export const pedirAyuda = (desafioId: number, mensajeEstudiante?: string) =>
  cliente
    .post<RespuestaAyuda>(`/desafios/${desafioId}/ayuda`, mensajeEstudiante ? { mensaje_estudiante: mensajeEstudiante } : {})
    .then((r) => r.data);

export const valorarAyuda = (solicitudId: number, valor: 1 | -1) =>
  cliente.post<RespuestaValoracion>(`/ayudas/${solicitudId}/valoracion`, { valor }).then((r) => r.data);
