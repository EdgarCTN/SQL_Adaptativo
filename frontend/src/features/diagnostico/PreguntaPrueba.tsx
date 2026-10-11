import type { MotivoOmision, Pregunta } from "../../api/tiposLineaBase";
import type { RespuestaLocal } from "./borrador";
import { respuestaVacia } from "./validacion";

interface Props {
  pregunta: Pregunta;
  respuesta?: RespuestaLocal;
  escala: Record<string, string>;
  motivos: MotivoOmision[];
  error?: string;
  alCambiar: (r: RespuestaLocal) => void;
}

/** Preguntas de la Parte 2: respuesta, confianza 1-5 y «Omitir por…». */
export default function PreguntaPrueba({ pregunta, respuesta, escala, motivos, error, alCambiar }: Props) {
  const actual = respuesta ?? respuestaVacia();
  const omitida = actual.omitir !== null;
  const elegida = pregunta.opciones.find((o) => o.id === actual.opciones[0]);
  const confianzaDeshabilitada = omitida || !elegida || !!elegida.es_no_se;
  const tituloId = `titulo-${pregunta.id}`;
  const errorId = `error-${pregunta.id}`;
  const niveles = Object.keys(escala).sort();

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

      <div
        role="radiogroup"
        aria-labelledby={tituloId}
        aria-describedby={error ? errorId : undefined}
        className="mt-3 space-y-2"
      >
        {pregunta.opciones.map((op) => (
          <label
            key={op.id}
            className={`flex items-start gap-2 text-sm ${omitida ? "cursor-not-allowed opacity-50" : "cursor-pointer"}`}
          >
            <input
              type="radio"
              name={`q-${pregunta.id}`}
              checked={actual.opciones[0] === op.id}
              disabled={omitida}
              onChange={() =>
                alCambiar({ opciones: [op.id], confianza: op.es_no_se ? null : actual.confianza, omitir: null })
              }
              className="mt-1"
            />
            {op.es_no_se ? (
              <span>{op.texto}</span>
            ) : (
              <code className="whitespace-pre-wrap break-words rounded bg-slate-50 px-1.5 py-0.5 font-mono text-xs text-slate-800">
                {op.texto}
              </code>
            )}
          </label>
        ))}
      </div>

      <div className="mt-4" role="radiogroup" aria-label={`Confianza en la pregunta ${pregunta.id}`}>
        <p className="text-sm font-medium text-slate-700">¿Qué tan seguro/a estás de tu respuesta?</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {niveles.map((n) => (
            <label
              key={n}
              className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs ${
                confianzaDeshabilitada
                  ? "cursor-not-allowed border-slate-200 opacity-50"
                  : "cursor-pointer border-slate-300 hover:bg-slate-50"
              } ${actual.confianza === Number(n) ? "border-indigo-500 bg-indigo-50" : ""}`}
            >
              <input
                type="radio"
                name={`conf-${pregunta.id}`}
                checked={actual.confianza === Number(n)}
                disabled={confianzaDeshabilitada}
                onChange={() => alCambiar({ ...actual, confianza: Number(n) })}
              />
              <span>
                {n} · {escala[n]}
              </span>
            </label>
          ))}
        </div>
        {!omitida && elegida?.es_no_se && (
          <p className="mt-1 text-xs text-slate-500">Con «No sé» no hace falta indicar la confianza.</p>
        )}
        {!omitida && !elegida && <p className="mt-1 text-xs text-slate-500">Primero elige una respuesta.</p>}
      </div>

      <div className="mt-4 border-t border-slate-100 pt-3" role="radiogroup" aria-label={`Omitir la pregunta ${pregunta.id}`}>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
          <span className="font-medium text-slate-700">Omitir por:</span>
          {motivos.map((m) => (
            <label key={m.codigo} className="flex cursor-pointer items-center gap-1.5">
              <input
                type="radio"
                name={`omitir-${pregunta.id}`}
                checked={actual.omitir === m.codigo}
                onChange={() => alCambiar({ opciones: [], confianza: null, omitir: m.codigo })}
              />
              {m.texto}
            </label>
          ))}
          {omitida && (
            <button
              type="button"
              onClick={() => alCambiar(respuestaVacia())}
              className="rounded text-xs font-medium text-indigo-700 underline"
            >
              Quitar omisión y responder
            </button>
          )}
        </div>
      </div>

      {error && (
        <p id={errorId} role="alert" className="mt-2 text-sm text-red-700">
          {error}
        </p>
      )}
    </section>
  );
}
