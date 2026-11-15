import { useId } from "react";

import { MSG_RANGO_INVERTIDO, rangoInvertido } from "./fechas";

interface Props {
  desde: string;
  hasta: string;
  onCambio: (desde: string, hasta: string) => void;
}

/** Rango de fechas (días completos). Avisa si el inicio es posterior al fin; quien lo usa no debe consultar entonces. */
export default function FiltroFechas({ desde, hasta, onCambio }: Props) {
  const id = useId();
  const invalido = rangoInvertido(desde, hasta);
  const clase =
    "mt-1 block rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200";
  return (
    <>
      <div>
        <label htmlFor={`${id}-desde`} className="block text-sm font-medium text-slate-700">
          Desde
        </label>
        <input
          id={`${id}-desde`}
          type="date"
          value={desde}
          max={hasta || undefined}
          onChange={(e) => onCambio(e.target.value, hasta)}
          aria-invalid={invalido}
          aria-describedby={invalido ? `${id}-error` : undefined}
          className={clase}
        />
      </div>
      <div>
        <label htmlFor={`${id}-hasta`} className="block text-sm font-medium text-slate-700">
          Hasta
        </label>
        <input
          id={`${id}-hasta`}
          type="date"
          value={hasta}
          min={desde || undefined}
          onChange={(e) => onCambio(desde, e.target.value)}
          aria-invalid={invalido}
          aria-describedby={invalido ? `${id}-error` : undefined}
          className={clase}
        />
      </div>
      {invalido && (
        <p id={`${id}-error`} role="alert" className="w-full text-sm text-red-700">
          {MSG_RANGO_INVERTIDO}
        </p>
      )}
    </>
  );
}
