import { useCallback } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { listarDesafios } from "../../api/desafios";
import { useCarga } from "../../api/useCarga";
import EstadoContenedor from "../../components/EstadoContenedor";
import { ESTILO_ESTADO, ETIQUETA_DIFICULTAD, ETIQUETA_ESTADO, formatearDuracion } from "./formatos";

export default function DesafiosPage() {
  const [params, setParams] = useSearchParams();
  const concepto = params.get("concepto") ?? "";
  const cargador = useCallback(() => listarDesafios(concepto || undefined), [concepto]);
  const { datos, cargando, error, recargar } = useCarga(cargador);

  const cambiarConcepto = (valor: string) => setParams(valor ? { concepto: valor } : {}, { replace: true });

  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-bold text-slate-900">Desafíos</h1>
      <p className="mt-1 text-sm text-slate-600">Elige un desafío y escribe la consulta SQL que resuelve el enunciado.</p>

      {datos && datos.conceptos.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <label htmlFor="filtro-concepto" className="text-sm font-medium text-slate-700">
            Concepto
          </label>
          <select
            id="filtro-concepto"
            value={concepto}
            onChange={(e) => cambiarConcepto(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm"
          >
            <option value="">Todos los conceptos</option>
            {datos.conceptos.map((c) => (
              <option key={c.codigo} value={c.codigo}>
                {c.nombre}
              </option>
            ))}
          </select>
        </div>
      )}

      <div className="mt-4" aria-busy={cargando}>
        <EstadoContenedor
          cargando={cargando && !datos}
          error={error}
          vacio={!!datos && datos.total === 0}
          mensajeVacio={datos?.mensaje ?? "Todavía no hay desafíos disponibles."}
          onReintentar={() => void recargar()}
        >
          <div className="space-y-6">
            {datos?.grupos.map((g) => (
              <section key={g.dificultad} aria-labelledby={`grupo-${g.dificultad}`}>
                <h2 id={`grupo-${g.dificultad}`} className="text-lg font-semibold text-slate-900">
                  {ETIQUETA_DIFICULTAD[g.dificultad]}
                </h2>
                {g.desafios.length === 0 ? (
                  <p className="mt-2 text-sm text-slate-500">No hay desafíos de esta dificultad con el filtro elegido.</p>
                ) : (
                  <ul className="mt-2 grid gap-3 sm:grid-cols-2">
                    {g.desafios.map((d) => (
                      <li key={d.id}>
                        <Link
                          to={`/desafios/${d.id}`}
                          className="block h-full rounded-xl border border-slate-200 bg-white p-4 hover:border-indigo-400 hover:shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500"
                        >
                          <span className="flex items-start justify-between gap-2">
                            <span className="font-semibold text-slate-900">{d.titulo}</span>
                            <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${ESTILO_ESTADO[d.estado]}`}>
                              {ETIQUETA_ESTADO[d.estado]}
                            </span>
                          </span>
                          {d.verificacion && (
                            <span className="mt-2 inline-block rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-900">
                              Verificación
                            </span>
                          )}
                          <span className="mt-2 block text-sm text-slate-600">
                            {d.concepto.nombre} · Tiempo de referencia: {formatearDuracion(d.tiempo_referencia_seg)}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            ))}
          </div>
        </EstadoContenedor>
      </div>
    </div>
  );
}
