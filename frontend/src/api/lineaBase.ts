import { cliente } from "./cliente";
import type {
  Cuestionario,
  EnvioRespuestas,
  EstadoLineaBase,
  ResultadoConsentimiento,
  ResultadoEnvio,
} from "./tiposLineaBase";

export const obtenerEstado = () => cliente.get<EstadoLineaBase>("/linea-base/estado").then((r) => r.data);

export const registrarConsentimiento = (acepta: boolean) =>
  cliente.post<ResultadoConsentimiento>("/linea-base/consentimiento", { acepta }).then((r) => r.data);

export const obtenerCuestionario = () =>
  cliente.get<Cuestionario>("/linea-base/cuestionario").then((r) => r.data);

export const enviarRespuestas = (envio: EnvioRespuestas) =>
  cliente.post<ResultadoEnvio>("/linea-base/respuestas", envio).then((r) => r.data);
