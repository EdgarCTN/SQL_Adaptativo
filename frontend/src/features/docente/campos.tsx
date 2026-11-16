import { TextareaHTMLAttributes, useId } from "react";

interface Comunes {
  etiqueta: string;
  error?: string;
  ayuda?: string;
}

function Mensajes({ id, error, ayuda }: { id: string; error?: string; ayuda?: string }) {
  if (error) {
    return (
      <p id={`${id}-error`} className="mt-1 text-sm text-red-700">
        {error}
      </p>
    );
  }
  return ayuda ? (
    <p id={`${id}-ayuda`} className="mt-1 text-xs text-slate-500">
      {ayuda}
    </p>
  ) : null;
}

interface PropsArea extends Comunes, Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "onChange" | "value"> {
  valor: string;
  alCambiar: (valor: string) => void;
  filas?: number;
  codigo?: boolean;
}

export function CampoArea({ etiqueta, valor, alCambiar, error, ayuda, filas = 4, codigo = false, ...resto }: PropsArea) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {etiqueta}
      </label>
      <textarea
        {...resto}
        id={id}
        rows={filas}
        value={valor}
        spellCheck={codigo ? false : resto.spellCheck}
        onChange={(e) => alCambiar(e.target.value)}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : ayuda ? `${id}-ayuda` : undefined}
        className={`mt-1 block w-full rounded-lg border px-3 py-2 text-sm shadow-sm ${codigo ? "font-mono text-xs" : ""} ${
          error ? "border-red-400 bg-red-50" : "border-slate-300 bg-white"
        }`}
      />
      <Mensajes id={id} error={error} ayuda={ayuda} />
    </div>
  );
}

interface PropsSeleccion extends Comunes {
  valor: string;
  alCambiar: (valor: string) => void;
  opciones: { valor: string; etiqueta: string }[];
  placeholder: string;
}

export function CampoSeleccion({ etiqueta, valor, alCambiar, error, ayuda, opciones, placeholder }: PropsSeleccion) {
  const id = useId();
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {etiqueta}
      </label>
      <select
        id={id}
        value={valor}
        onChange={(e) => alCambiar(e.target.value)}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : ayuda ? `${id}-ayuda` : undefined}
        className={`mt-1 block w-full rounded-lg border px-3 py-2 text-sm shadow-sm ${error ? "border-red-400 bg-red-50" : "border-slate-300 bg-white"}`}
      >
        <option value="">{placeholder}</option>
        {opciones.map((o) => (
          <option key={o.valor} value={o.valor}>
            {o.etiqueta}
          </option>
        ))}
      </select>
      <Mensajes id={id} error={error} ayuda={ayuda} />
    </div>
  );
}
