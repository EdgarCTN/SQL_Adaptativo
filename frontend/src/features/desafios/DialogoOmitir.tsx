import { useEffect, useId, useRef, useState } from "react";

import type { MotivoOmision } from "../../api/tiposDesafios";

interface Props {
  ocupado?: boolean;
  onConfirmar: (motivo: MotivoOmision) => void;
  onCancelar: () => void;
}

const OPCIONES: { valor: MotivoOmision; texto: string }[] = [
  { valor: "muy_facil", texto: "Muy fácil" },
  { valor: "muy_dificil", texto: "Muy difícil" },
];

/** Diálogo modal para omitir un desafío: hay que elegir el motivo. Escape cierra, Tab queda dentro y el foco vuelve al cerrar. */
export default function DialogoOmitir({ ocupado = false, onConfirmar, onCancelar }: Props) {
  const idTitulo = useId();
  const idMensaje = useId();
  const [motivo, setMotivo] = useState<MotivoOmision | null>(null);
  const [sinElegir, setSinElegir] = useState(false);
  const raiz = useRef<HTMLDivElement>(null);
  const alCancelar = useRef(onCancelar);
  alCancelar.current = onCancelar;

  useEffect(() => {
    const previo = document.activeElement as HTMLElement | null;
    raiz.current?.querySelector<HTMLElement>("input")?.focus();
    return () => previo?.focus?.();
  }, []);

  const alTeclear = (e: React.KeyboardEvent) => {
    if (e.key === "Escape" && !ocupado) {
      e.stopPropagation();
      alCancelar.current();
    } else if (e.key === "Tab" && raiz.current) {
      const orden = Array.from(raiz.current.querySelectorAll<HTMLElement>("input, button")).filter(
        (el) => !(el as HTMLInputElement | HTMLButtonElement).disabled,
      );
      if (orden.length === 0) return e.preventDefault();
      const i = orden.indexOf(document.activeElement as HTMLElement);
      const siguiente = e.shiftKey ? (i <= 0 ? orden.length - 1 : i - 1) : i === orden.length - 1 ? 0 : i + 1;
      e.preventDefault();
      orden[siguiente].focus();
    }
  };

  const confirmar = () => {
    if (!motivo) {
      setSinElegir(true);
      return;
    }
    onConfirmar(motivo);
  };

  return (
    <div
      className="fixed inset-0 z-40 flex items-center justify-center bg-slate-900/50 p-4"
      onClick={() => !ocupado && onCancelar()}
      onKeyDown={alTeclear}
    >
      <div
        ref={raiz}
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        aria-describedby={idMensaje}
        className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id={idTitulo} className="text-lg font-bold text-slate-900">
          ¿Omitir este desafío?
        </h2>
        <p id={idMensaje} className="mt-2 text-sm text-slate-700">
          No cuenta como resuelto ni como fallo. Cuéntanos por qué lo omites:
        </p>
        <fieldset className="mt-3" disabled={ocupado}>
          <legend className="sr-only">Motivo de la omisión</legend>
          {OPCIONES.map((o) => (
            <label key={o.valor} className="mt-1 flex items-center gap-2 text-sm text-slate-800">
              <input
                type="radio"
                name="motivo-omision"
                value={o.valor}
                checked={motivo === o.valor}
                onChange={() => {
                  setMotivo(o.valor);
                  setSinElegir(false);
                }}
              />
              {o.texto}
            </label>
          ))}
        </fieldset>
        {sinElegir && (
          <p role="alert" className="mt-2 text-sm text-red-700">
            Elige si te pareció muy fácil o muy difícil.
          </p>
        )}
        <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            disabled={ocupado}
            onClick={onCancelar}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          >
            Seguir intentando
          </button>
          <button
            type="button"
            disabled={ocupado}
            onClick={confirmar}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
          >
            {ocupado ? "Omitiendo…" : "Omitir desafío"}
          </button>
        </div>
      </div>
    </div>
  );
}
