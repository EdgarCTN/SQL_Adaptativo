import type { TablaEsquema } from "../../api/tiposLineaBase";

export default function EsquemaTablas({ tablas }: { tablas: TablaEsquema[] }) {
  if (!tablas.length) return null;
  return (
    <details open className="rounded-xl border border-slate-200 bg-white p-4">
      <summary className="cursor-pointer text-sm font-semibold text-slate-900">
        Esquema de la base de datos ({tablas.map((t) => t.nombre).join(", ")})
      </summary>
      <p className="mt-2 text-sm text-slate-600">Usa estas tablas para responder las preguntas de esta parte.</p>
      <div className="mt-3 space-y-4">
        {tablas.map((t) => (
          <div key={t.nombre} className="overflow-x-auto">
            <table className="min-w-full border-collapse text-left text-xs">
              <caption className="mb-1 text-left text-sm font-semibold text-slate-800">{t.nombre}</caption>
              <thead>
                <tr>
                  {t.columnas.map((c) => (
                    <th key={c} scope="col" className="border border-slate-300 bg-slate-100 px-2 py-1 font-semibold">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {t.filas.map((fila, i) => (
                  <tr key={i}>
                    {fila.map((celda, j) => (
                      <td key={j} className="border border-slate-300 px-2 py-1">
                        {celda}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </details>
  );
}
