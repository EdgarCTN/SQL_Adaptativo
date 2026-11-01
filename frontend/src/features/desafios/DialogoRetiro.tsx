import { useEffect, useId, useRef } from "react";

interface Props {
  texto: string;
  ocupado?: boolean;
  onAceptar: () => void;
  onMantener: () => void;
  onCerrar: () => void; // decidir después: el aviso sigue disponible en la lista de desafíos
}

/** R13 (pregunta 3.4 = «preguntar»): diálogo modal accesible. Escape o «Decidir después» lo cierra sin responder. */
export default function DialogoRetiro({ texto, ocupado = false, onAceptar, onMantener, onCerrar }: Props) {
  const idTitulo = useId();
  const idTexto = useId();
  const botones = useRef<(HTMLButtonElement | null)[]>([]);

  useEffect(() => {
    const previo = document.activeElement as HTMLElement | null;
    botones.current[0]?.focus();
    return () => previo?.focus?.();
  }, []);

  const alTeclear = (e: React.KeyboardEvent) => {
    if (e.key === "Escape" && !ocupado) {
      e.stopPropagation();
      onCerrar();
    } else if (e.key === "Tab") {
      const orden = botones.current.filter((b): b is HTMLButtonElement => !!b && !b.disabled);
      if (orden.length === 0) return e.preventDefault();
      const i = orden.indexOf(document.activeElement as HTMLButtonElement);
      const siguiente = e.shiftKey ? (i <= 0 ? orden.length - 1 : i - 1) : i === orden.length - 1 ? 0 : i + 1;
      e.preventDefault();
      orden[siguiente].focus();
    }
  };

  const base = "rounded-lg px-4 py-2 text-sm font-semibold disabled:opacity-60";
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/50 p-4" onKeyDown={alTeclear}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        aria-describedby={idTexto}
        className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"
      >
        <h2 id={idTitulo} className="text-lg font-bold text-slate-900">
          ¿Menos ayuda en este tema?
        </h2>
        <p id={idTexto} className="mt-2 text-sm text-slate-700">
          {texto}
        </p>
        <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:justify-end">
          <button
            ref={(el) => (botones.current[0] = el)}
            type="button"
            disabled={ocupado}
            onClick={onMantener}
            className={`${base} border border-slate-300 text-slate-700 hover:bg-slate-50`}
          >
            Seguir como hasta ahora
          </button>
          <button
            ref={(el) => (botones.current[1] = el)}
            type="button"
            disabled={ocupado}
            onClick={onAceptar}
            className={`${base} bg-indigo-600 text-white hover:bg-indigo-700`}
          >
            {ocupado ? "Guardando…" : "Sí, menos ayuda"}
          </button>
          <button
            ref={(el) => (botones.current[2] = el)}
            type="button"
            disabled={ocupado}
            onClick={onCerrar}
            className={`${base} text-slate-600 underline`}
          >
            Decidir después
          </button>
        </div>
      </div>
    </div>
  );
}
