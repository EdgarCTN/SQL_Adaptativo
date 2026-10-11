import type { Opcion, Pregunta } from "../../api/tiposLineaBase";
import type { RespuestaLocal } from "./borrador";
import { respuestaVacia } from "./validacion";

interface Props {
  pregunta: Pregunta;
  respuesta?: RespuestaLocal;
  error?: string;
  alCambiar: (r: RespuestaLocal) => void;
}

/** Preguntas de las Partes 1 y 3: opción única o selección múltiple con opción excluyente («Ninguna»). */
export default function PreguntaSeleccion({ pregunta, respuesta, error, alCambiar }: Props) {
  const actual = respuesta ?? respuestaVacia();
  const multiple = pregunta.tipo === "multiple";
  const tituloId = `titulo-${pregunta.id}`;
  const errorId = `error-${pregunta.id}`;

  const elegir = (op: Opcion) => alCambiar({ ...actual, opciones: [op.id] });

  const alternar = (op: Opcion, marcada: boolean) => {
    if (!marcada) return alCambiar({ ...actual, opciones: actual.opciones.filter((id) => id !== op.id) });
    if (op.excluyente) return alCambiar({ ...actual, opciones: [op.id] }); // «Ninguna» desmarca todo lo demás
    const sinExcluyentes = actual.opciones.filter((id) => !pregunta.opciones.find((o) => o.id === id)?.excluyente);
    alCambiar({ ...actual, opciones: [...sinExcluyentes, op.id] });
  };

  return (
    <section
      id={`pregunta-${pregunta.id}`}
      tabIndex={-1}
      className={`rounded-xl border p-4 ${error ? "border-red-400 bg-red-50" : "border-slate-200 bg-white"}`}
    >
      <p id={tituloId} className="text-sm font-semibold text-slate-900">
        <span className="mr-2 rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">{pregunta.id}</span>
        {pregunta.enunciado}
      </p>
      {pregunta.nota && <p className="mt-1 text-xs text-slate-500">{pregunta.nota}</p>}
      <div
        role={multiple ? "group" : "radiogroup"}
        aria-labelledby={tituloId}
        aria-describedby={error ? errorId : undefined}
        className="mt-3 space-y-2"
      >
        {pregunta.opciones.map((op) => {
          const marcada = actual.opciones.includes(op.id);
          return (
            <label key={op.id} className="flex cursor-pointer items-start gap-2 text-sm">
              <input
                type={multiple ? "checkbox" : "radio"}
                name={`q-${pregunta.id}`}
                checked={marcada}
                onChange={(e) => (multiple ? alternar(op, e.target.checked) : elegir(op))}
                className="mt-1"
              />
              <span>{op.texto}</span>
            </label>
          );
        })}
      </div>
      {error && (
        <p id={errorId} role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </section>
  );
}
