import { cliente } from "./cliente";
import type { Evolucion, FiltrosEvolucion, FiltrosIntentos, ListaIntentos, ResumenProgreso } from "./tiposProgreso";

export const obtenerResumenProgreso = () => cliente.get<ResumenProgreso>("/progreso/resumen").then((r) => r.data);

export const listarIntentos = (f: FiltrosIntentos) =>
  cliente
    .get<ListaIntentos>("/progreso/intentos", {
      params: { desafio_id: f.desafioId, desde: f.desde, hasta: f.hasta, pagina: f.pagina, tam: f.tam },
    })
    .then((r) => r.data);

export const obtenerEvolucion = (f: FiltrosEvolucion) =>
  cliente
    .get<Evolucion>("/progreso/evolucion", { params: { concepto: f.concepto, desde: f.desde, hasta: f.hasta } })
    .then((r) => r.data);
