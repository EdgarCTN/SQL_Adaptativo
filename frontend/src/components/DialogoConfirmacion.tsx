import { useEffect, useId, useRef } from "react";

interface Props {
  titulo: string;
  mensaje: string;
  etiquetaConfirmar: string;
  etiquetaCancelar: string;
  ocupado?: boolean;
  onConfirmar: () => void;
  onCancelar: () => void;
}

/** Diálogo modal accesible: foco en «cancelar», Escape cierra, Tab queda dentro y el foco vuelve al cerrar. */
export default function DialogoConfirmacion({
  titulo,
  mensaje,
  etiquetaConfirmar,
  etiquetaCancelar,
  ocupado = false,
  onConfirmar,
  onCancelar,
}: Props) {
  const idTitulo = useId();
  const idMensaje = useId();
  const cancelar = useRef<HTMLButtonElement>(null);
  const confirmar = useRef<HTMLButtonElement>(null);
  const alCancelar = useRef(onCancelar);
  alCancelar.current = onCancelar;

  useEffect(() => {
    const previo = document.activeElement as HTMLElement | null;
    cancelar.current?.focus();
    return () => previo?.focus?.();
  }, []);

  const alTeclear = (e: React.KeyboardEvent) => {
    if (e.key === "Escape" && !ocupado) {
      e.stopPropagation();
      alCancelar.current();
    } else if (e.key === "Tab") {
      const orden = [cancelar.current, confirmar.current].filter((b): b is HTMLButtonElement => !!b && !b.disabled);
      if (orden.length === 0) return e.preventDefault();
      const i = orden.indexOf(document.activeElement as HTMLButtonElement);
      const siguiente = e.shiftKey ? (i <= 0 ? orden.length - 1 : i - 1) : i === orden.length - 1 ? 0 : i + 1;
      e.preventDefault();
      orden[siguiente].focus();
    }
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/50 p-4"
      onClick={() => !ocupado && onCancelar()}
      onKeyDown={alTeclear}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        aria-describedby={idMensaje}
        className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id={idTitulo} className="text-lg font-bold text-slate-900">
          {titulo}
        </h2>
        <p id={idMensaje} className="mt-2 text-sm text-slate-700">
          {mensaje}
        </p>
        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            ref={cancelar}
            type="button"
            disabled={ocupado}
            onClick={onCancelar}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          >
            {etiquetaCancelar}
          </button>
          <button
            ref={confirmar}
            type="button"
            disabled={ocupado}
            onClick={onConfirmar}
            className="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-60"
          >
            {ocupado ? "Abandonando…" : etiquetaConfirmar}
          </button>
        </div>
      </div>
    </div>
  );
}
