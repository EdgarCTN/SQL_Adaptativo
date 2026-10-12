import type { CeldaResultado } from "../../api/tiposDesafios";

interface Props {
  columnas: string[];
  filas: CeldaResultado[][];
  titulo: string;
}

export default function TablaResultado({ columnas, filas, titulo }: Props) {
  if (columnas.length === 0) return null;
  return (
    <div className="mt-3 overflow-x-auto rounded-lg border border-slate-300 bg-white">
      <table className="min-w-full border-collapse text-left font-mono text-xs">
        <caption className="sr-only">{titulo}</caption>
        <thead>
          <tr>
            {columnas.map((c, i) => (
              <th key={i} scope="col" className="border-b border-slate-300 bg-slate-100 px-2 py-1 font-semibold">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.length === 0 ? (
            <tr>
              <td colSpan={columnas.length} className="px-2 py-2 font-sans italic text-slate-500">
                Sin filas.
              </td>
            </tr>
          ) : (
            filas.map((fila, i) => (
              <tr key={i} className="odd:bg-white even:bg-slate-50">
                {fila.map((celda, j) => (
                  <td key={j} className="border-t border-slate-200 px-2 py-1">
                    {celda === null ? <em className="font-sans text-slate-400">NULL</em> : String(celda)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
