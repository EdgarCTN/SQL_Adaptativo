import { useState } from "react";

import type { OfertaAyuda as Oferta } from "../../api/tiposDesafios";

interface Props {
  oferta: Oferta;
  pidiendo: boolean;
  onAceptar: () => Promise<boolean>;
}

/** Tarjeta «¿Quieres una pista?» (preferencia 3.3 = ofrecer) o aviso de ayuda mostrada sola. Se reinicia en cada envío (key). */
export default function OfertaAyuda({ oferta, pidiendo, onAceptar }: Props) {
  const [cerrada, setCerrada] = useState(false);
  if (cerrada) return null;

  if (oferta.modo === "mostrar_sola") {
    return (
      <p role="status" className="rounded-xl border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-900">
        {oferta.texto} Está en la sección «Ayuda», más abajo.
      </p>
    );
  }
  return (
    <section aria-label="Oferta de ayuda" className="rounded-xl border border-indigo-200 bg-indigo-50 p-4">
      <p className="text-sm font-semibold text-indigo-900">{oferta.texto}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <button
          type="button"
          disabled={pidiendo}
          onClick={() => void onAceptar().then((ok) => ok && setCerrada(true))}
          className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
        >
          {pidiendo ? "Buscando ayuda…" : (oferta.boton ?? "Ver la ayuda")}
        </button>
        <button
          type="button"
          onClick={() => setCerrada(true)}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          {oferta.boton_rechazo ?? "Ahora no"}
        </button>
      </div>
    </section>
  );
}
