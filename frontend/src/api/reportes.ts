import { cliente } from "./cliente";
import type { FiltrosReporte, Reporte, TipoExportacion } from "./tiposReportes";

export const obtenerReporte = (f: FiltrosReporte) =>
  cliente.get<Reporte>("/reportes", { params: { desde: f.desde, hasta: f.hasta } }).then((r) => r.data);

/** Pide el CSV (o el ZIP) con la sesión actual y lo baja con el nombre que indica el servidor. */
export async function descargarExportacion(tipo: TipoExportacion, f: FiltrosReporte): Promise<void> {
  const r = await cliente.get<Blob>("/reportes/exportar", {
    params: { tipo, desde: f.desde, hasta: f.hasta },
    responseType: "blob",
    timeout: 60000,
  });
  const cabecera = String(r.headers["content-disposition"] ?? "");
  const nombre = /filename="?([^";]+)"?/.exec(cabecera)?.[1] ?? (tipo === "todos" ? "exportacion.zip" : `${tipo}.csv`);
  const url = URL.createObjectURL(r.data);
  try {
    const enlace = document.createElement("a");
    enlace.href = url;
    enlace.download = nombre;
    document.body.appendChild(enlace);
    enlace.click();
    enlace.remove();
  } finally {
    URL.revokeObjectURL(url);
  }
}
