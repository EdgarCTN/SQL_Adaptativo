import { cliente } from "./cliente";
import type {
  DesafioDetalle,
  InicioSesion,
  ListaDesafios,
  ResultadoAbandono,
  ResultadoIntento,
} from "./tiposDesafios";

export const listarDesafios = (concepto?: string) =>
  cliente.get<ListaDesafios>("/desafios", { params: concepto ? { concepto } : undefined }).then((r) => r.data);

export const obtenerDesafio = (id: number) => cliente.get<DesafioDetalle>(`/desafios/${id}`).then((r) => r.data);

export const iniciarDesafio = (id: number) =>
  cliente.post<InicioSesion>(`/desafios/${id}/iniciar`).then((r) => r.data);

export const enviarIntento = (id: number, codigo: string) =>
  cliente.post<ResultadoIntento>(`/desafios/${id}/intentos`, { codigo }).then((r) => r.data);

export const abandonarDesafio = (id: number) =>
  cliente.post<ResultadoAbandono>(`/desafios/${id}/abandonar`).then((r) => r.data);
