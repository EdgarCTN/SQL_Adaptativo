import { cliente } from "./cliente";
import type { ResumenProgreso } from "./tiposProgreso";

export const obtenerResumenProgreso = () => cliente.get<ResumenProgreso>("/progreso/resumen").then((r) => r.data);
