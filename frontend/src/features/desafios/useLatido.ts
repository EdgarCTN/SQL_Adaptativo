import { useEffect, useRef } from "react";

import { enviarLatido } from "../../api/desafios";

const CADA_MS = 15_000; // un latido cada 15 s
const INACTIVIDAD_MAX_MS = 30_000; // sin actividad en los últimos 30 s no se envía
const EVENTOS = ["keydown", "mousemove", "mousedown", "touchstart", "focus", "focusin"] as const;

/**
 * Envía un latido cada 15 s mientras `activo`, solo si la pestaña está visible y hubo actividad
 * (teclado, ratón o foco) en los últimos 30 s. Cualquier fallo se ignora en silencio.
 */
export function useLatido(desafioId: number, activo: boolean): void {
  const ultimaActividad = useRef(Date.now());
  const enVuelo = useRef(false);

  useEffect(() => {
    if (!activo) return;
    const marcar = () => {
      ultimaActividad.current = Date.now();
    };
    const alCambiarVisibilidad = () => {
      if (document.visibilityState === "visible") marcar();
    };
    marcar();
    for (const e of EVENTOS) window.addEventListener(e, marcar, { passive: true, capture: true });
    document.addEventListener("visibilitychange", alCambiarVisibilidad);

    const temporizador = window.setInterval(() => {
      if (document.visibilityState !== "visible" || enVuelo.current) return;
      if (Date.now() - ultimaActividad.current > INACTIVIDAD_MAX_MS) return;
      enVuelo.current = true;
      enviarLatido(desafioId)
        .catch(() => {
          /* un latido fallido no se muestra ni se reintenta */
        })
        .finally(() => {
          enVuelo.current = false;
        });
    }, CADA_MS);

    return () => {
      window.clearInterval(temporizador);
      for (const e of EVENTOS) window.removeEventListener(e, marcar, true);
      document.removeEventListener("visibilitychange", alCambiarVisibilidad);
    };
  }, [desafioId, activo]);
}
