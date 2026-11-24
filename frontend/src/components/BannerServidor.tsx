import { useEffect, useRef, useState } from "react";

import { useServidor } from "../api/servidor";

const CASI_LISTO_TRAS_S = 45; // a partir de aquí se añade «Casi listo…»
const LISTO_VISIBLE_MS = 2500; // cuánto se muestra «Servidor listo.»

/** Aviso global del arranque en frío: el servidor gratuito está despertando (no es un error). */
export default function BannerServidor() {
  const { estado, segundos, reintentar } = useServidor();
  const anterior = useRef(estado);
  const [mostrarListo, setMostrarListo] = useState(false);

  // «Servidor listo.» solo se muestra si antes se vio «Despertando…»; se oculta a los 2,5 s.
  useEffect(() => {
    const previo = anterior.current;
    anterior.current = estado;
    if (previo === "despertando" && estado === "listo") {
      setMostrarListo(true);
      const temporizador = window.setTimeout(() => setMostrarListo(false), LISTO_VISIBLE_MS);
      return () => window.clearTimeout(temporizador);
    }
    setMostrarListo(false);
  }, [estado]);

  return (
    <>
      {/* La región existe siempre para que los lectores de pantalla anuncien sus cambios. */}
      <div role="status" aria-live="polite" className="mx-auto w-full max-w-3xl px-4 empty:hidden">
        {estado === "despertando" && (
          <div className="mt-3 flex items-start gap-3 rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-900">
            <span
              aria-hidden="true"
              className="mt-0.5 h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-indigo-300 border-t-indigo-700 motion-reduce:animate-none"
            />
            <div className="min-w-0 flex-1">
              <p className="font-semibold">Despertando el servidor…</p>
              <p className="mt-1">
                Esta plataforma usa un servidor gratuito que se apaga cuando no se usa. Puede tardar hasta 1 minuto en despertar. No es un
                error: no cierres la página, continuará sola.
              </p>
              {/* El contador no se anuncia cada segundo a los lectores de pantalla. */}
              <p aria-hidden="true" className="mt-1 text-xs text-indigo-700">
                Esperando… {segundos} s
              </p>
              {segundos >= CASI_LISTO_TRAS_S && <p className="mt-1 text-xs font-medium text-indigo-800">Casi listo, gracias por la paciencia.</p>}
            </div>
          </div>
        )}
        {estado === "listo" && mostrarListo && (
          <div className="mt-3 rounded-lg border border-green-300 bg-green-50 p-3 text-sm font-medium text-green-900">Servidor listo.</div>
        )}
      </div>

      {estado === "caido" && (
        <div className="mx-auto w-full max-w-3xl px-4">
          <div role="alert" className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            <p>No logramos despertar el servidor. Puede ser un problema temporal.</p>
            <button
              type="button"
              onClick={reintentar}
              className="rounded-lg border border-red-300 bg-white px-3 py-1.5 font-semibold text-red-800 hover:bg-red-100"
            >
              Reintentar
            </button>
          </div>
        </div>
      )}
    </>
  );
}
