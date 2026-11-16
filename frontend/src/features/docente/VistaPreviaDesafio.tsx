import type { Dificultad } from "../../api/tiposDesafios";
import { ETIQUETA_DIFICULTAD, formatearDuracion } from "../desafios/formatos";

interface Props {
  titulo: string;
  concepto: string;
  dificultad: Dificultad | "";
  tiempoSeg: number | null;
  enunciado: string;
  recursos: string[];
  esquema: string;
}

/** Réplica de lo que el estudiante ve al abrir el desafío (sin solución, setup ni ayudas). */
export default function VistaPreviaDesafio({ titulo, concepto, dificultad, tiempoSeg, enunciado, recursos, esquema }: Props) {
  return (
    <article aria-label="Vista previa del desafío" className="rounded-xl border-2 border-dashed border-indigo-300 bg-slate-50 p-4">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-indigo-700">Así lo ve el estudiante</p>
      <header>
        <h2 className="text-2xl font-bold text-slate-900">{titulo || "Sin título"}</h2>
        <p className="mt-1 flex flex-wrap gap-x-3 text-sm text-slate-600">
          <span>{concepto || "Sin concepto"}</span>
          <span>{dificultad ? ETIQUETA_DIFICULTAD[dificultad] : "Sin dificultad"}</span>
          {tiempoSeg !== null && <span>Tiempo de referencia: {formatearDuracion(tiempoSeg)}</span>}
        </p>
      </header>
      <section className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="text-base font-semibold text-slate-900">Enunciado</h3>
        <p className="mt-1 whitespace-pre-line text-sm text-slate-800">{enunciado || "Todavía no hay enunciado."}</p>
        {recursos.length > 0 && (
          <>
            <h4 className="mt-3 text-sm font-semibold text-slate-900">Recursos</h4>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">
              {recursos.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </>
        )}
      </section>
      <section className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="text-base font-semibold text-slate-900">Esquema de la base de datos</h3>
        <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-900 p-3 font-mono text-xs text-slate-100">{esquema || "Todavía no hay esquema."}</pre>
      </section>
    </article>
  );
}
