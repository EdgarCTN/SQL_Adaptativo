import { useEffect, useRef, useState } from "react";

export type TipoToast = "exito" | "error" | "info";

export interface ToastEntrada {
  id?: string;
  tipo: TipoToast;
  mensaje: string;
  accion?: { etiqueta: string; alClick: () => void };
  duracion?: number;
}

interface ToastData extends ToastEntrada {
  id: string;
}

const oyentes = new Set<(t: ToastData) => void>();
let contador = 0;

/** Se puede llamar desde cualquier parte (también desde el cliente axios). */
export function mostrarToast(t: ToastEntrada): void {
  const data: ToastData = { ...t, id: t.id ?? `t${++contador}` };
  oyentes.forEach((o) => o(data));
}

const ESTILOS: Record<TipoToast, string> = {
  exito: "border-green-300 bg-green-50 text-green-900",
  error: "border-red-300 bg-red-50 text-red-900",
  info: "border-indigo-300 bg-indigo-50 text-indigo-900",
};

export function ToastProvider() {
  const [toasts, setToasts] = useState<ToastData[]>([]);
  const timers = useRef(new Map<string, number>());

  const quitar = (id: string) => {
    const timer = timers.current.get(id);
    if (timer) window.clearTimeout(timer);
    timers.current.delete(id);
    setToasts((prev) => prev.filter((x) => x.id !== id));
  };

  useEffect(() => {
    const activos = timers.current;
    const alRecibir = (t: ToastData) => {
      setToasts((prev) => [...prev.filter((x) => x.id !== t.id), t]);
      const previo = activos.get(t.id);
      if (previo) window.clearTimeout(previo);
      const ms = t.duracion ?? (t.accion ? 12000 : 5000);
      activos.set(
        t.id,
        window.setTimeout(() => {
          activos.delete(t.id);
          setToasts((prev) => prev.filter((x) => x.id !== t.id));
        }, ms)
      );
    };
    oyentes.add(alRecibir);
    return () => {
      oyentes.delete(alRecibir);
      activos.forEach((timer) => window.clearTimeout(timer));
      activos.clear();
    };
  }, []);

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex flex-col items-center gap-2 p-4 sm:items-end"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          role={t.tipo === "error" ? "alert" : "status"}
          className={`pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg border p-3 text-sm shadow-lg ${ESTILOS[t.tipo]}`}
        >
          <p className="flex-1">{t.mensaje}</p>
          {t.accion && (
            <button
              type="button"
              className="rounded font-semibold underline"
              onClick={() => {
                quitar(t.id);
                t.accion?.alClick();
              }}
            >
              {t.accion.etiqueta}
            </button>
          )}
          <button
            type="button"
            aria-label="Cerrar aviso"
            className="rounded px-1 font-bold leading-none"
            onClick={() => quitar(t.id)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
