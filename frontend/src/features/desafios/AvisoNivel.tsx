import type { AjusteNivel } from "../../api/tiposDesafios";
import { textoAjusteNivel } from "./formatos";

/** Aviso en pantalla (sin notificaciones) cuando cambia el nivel de ayuda del concepto. */
export default function AvisoNivel({ ajuste }: { ajuste: AjusteNivel }) {
  const baja = ajuste.ns_nuevo < ajuste.ns_anterior;
  return (
    <div role="status" className="mt-3 rounded-lg border border-indigo-300 bg-white p-3 text-indigo-900">
      <p className="text-sm font-semibold">
        <span aria-hidden="true">{baja ? "↓" : "↑"}</span> {textoAjusteNivel(ajuste)}
      </p>
      <p className="mt-1 text-sm">{ajuste.motivo}</p>
    </div>
  );
}
