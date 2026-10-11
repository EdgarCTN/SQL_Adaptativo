import { InputHTMLAttributes, useId, useState } from "react";

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, "onChange" | "value"> {
  etiqueta: string;
  valor: string;
  alCambiar: (valor: string) => void;
  error?: string;
  ayuda?: string;
}

export default function CampoTexto({ etiqueta, valor, alCambiar, error, ayuda, type = "text", ...resto }: Props) {
  const id = useId();
  const [visible, setVisible] = useState(false);
  const esClave = type === "password";
  const descripcion = error ? `${id}-error` : ayuda ? `${id}-ayuda` : undefined;

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-700">
        {etiqueta}
      </label>
      <div className="relative mt-1">
        <input
          {...resto}
          id={id}
          type={esClave && visible ? "text" : type}
          value={valor}
          onChange={(e) => alCambiar(e.target.value)}
          aria-invalid={error ? true : undefined}
          aria-describedby={descripcion}
          className={`block w-full rounded-lg border px-3 py-2 text-sm shadow-sm ${esClave ? "pr-20" : ""} ${
            error ? "border-red-400 bg-red-50" : "border-slate-300 bg-white"
          }`}
        />
        {esClave && (
          <button
            type="button"
            onClick={() => setVisible((v) => !v)}
            aria-pressed={visible}
            className="absolute inset-y-0 right-2 my-1 rounded px-2 text-xs font-medium text-indigo-700 hover:bg-indigo-50"
          >
            {visible ? "Ocultar" : "Mostrar"}
          </button>
        )}
      </div>
      {error ? (
        <p id={`${id}-error`} className="mt-1 text-sm text-red-700">
          {error}
        </p>
      ) : (
        ayuda && (
          <p id={`${id}-ayuda`} className="mt-1 text-xs text-slate-500">
            {ayuda}
          </p>
        )
      )}
    </div>
  );
}
