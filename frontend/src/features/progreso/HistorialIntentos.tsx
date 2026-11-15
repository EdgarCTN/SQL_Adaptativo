import { useCallback, useId, useState } from "react";
import { Link } from "react-router-dom";

import { listarIntentos } from "../../api/progreso";
import { useCarga } from "../../api/useCarga";
import EstadoContenedor from "../../components/EstadoContenedor";
import FiltroFechas from "./FiltroFechas";
import { finDelDia, formatearFechaHora, inicioDelDia, rangoInvertido } from "./fechas";

const TAM = 10;
const TH = "px-4 py-2 font-medium";

export default function HistorialIntentos() {
  const id = useId();
  const [desafio, setDesafio] = useState(""); // id del desafío o vacío = todos
  const [entrada, setEntrada] = useState({ desde: "", hasta: "" });
  const [aplicado, setAplicado] = useState({ desde: "", hasta: "" });
  const [pagina, setPagina] = useState(1);

  const cargador = useCallback(
    () =>
      listarIntentos({
        desafioId: desafio ? Number(desafio) : undefined,
        desde: inicioDelDia(aplicado.desde),
        hasta: finDelDia(aplicado.hasta),
        pagina,
        tam: TAM,
      }),
    [desafio, aplicado, pagina],
  );
  const { datos, cargando, error, recargar } = useCarga(cargador);

  const hayFiltros = Boolean(desafio || entrada.desde || entrada.hasta);
  const opciones = datos?.desafios ?? [];

  const alCambiarDesafio = (valor: string) => {
    setDesafio(valor);
    setPagina(1);
  };
  const alCambiarFechas = (desde: string, hasta: string) => {
    setEntrada({ desde, hasta });
    if (!rangoInvertido(desde, hasta)) {
      setAplicado({ desde, hasta }); // con el rango al revés no se consulta
      setPagina(1);
    }
  };
  const limpiar = () => {
    setDesafio("");
    setEntrada({ desde: "", hasta: "" });
    setAplicado({ desde: "", hasta: "" });
    setPagina(1);
  };

  const sinResultados = datos !== null && datos.total === 0;
  const sinHistorial = sinResultados && !hayFiltros;

  return (
    <section aria-labelledby={`${id}-titulo`}>
      <h2 id={`${id}-titulo`} className="text-lg font-semibold text-slate-900">
        Historial de intentos
      </h2>
      <p className="mt-1 text-sm text-slate-600">Todos los envíos que has hecho, del más reciente al más antiguo.</p>

      {(opciones.length > 0 || hayFiltros) && (
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor={`${id}-desafio`} className="block text-sm font-medium text-slate-700">
              Desafío
            </label>
            <select
              id={`${id}-desafio`}
              value={desafio}
              onChange={(e) => alCambiarDesafio(e.target.value)}
              className="mt-1 block max-w-xs rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
            >
              <option value="">Todos los desafíos</option>
              {opciones.map((o) => (
                <option key={o.id} value={String(o.id)}>
                  {o.titulo}
                </option>
              ))}
            </select>
          </div>
          <FiltroFechas desde={entrada.desde} hasta={entrada.hasta} onCambio={alCambiarFechas} />
          {hayFiltros && (
            <button
              type="button"
              onClick={limpiar}
              className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Quitar filtros
            </button>
          )}
        </div>
      )}

      <div className="mt-4" aria-busy={cargando}>
        <EstadoContenedor
          cargando={cargando && !datos}
          error={error}
          onReintentar={() => void recargar()}
          vacio={sinResultados}
          mensajeVacio={
            sinHistorial
              ? "Todavía no has enviado ningún intento. Resuelve un desafío y aparecerá aquí."
              : "No hay intentos con esos filtros. Prueba con otro desafío u otro rango de fechas."
          }
        >
          {datos && datos.total > 0 && (
            <>
              <p role="status" className="mb-2 text-sm text-slate-600">
                {datos.total} {datos.total === 1 ? "intento" : "intentos"} · página {datos.pagina} de {datos.paginas}
              </p>
              <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Historial de tus intentos</caption>
                  <thead className="bg-slate-50 text-slate-600">
                    <tr>
                      <th scope="col" className={TH}>Fecha</th>
                      <th scope="col" className={TH}>Desafío</th>
                      <th scope="col" className={TH}>Envío n.º</th>
                      <th scope="col" className={TH}>Resultado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {datos.intentos.map((i) => (
                      <tr key={i.id} className="border-t border-slate-100 align-top">
                        <td className="whitespace-nowrap px-4 py-2 text-slate-700">{formatearFechaHora(i.fecha)}</td>
                        <td className="px-4 py-2">
                          <Link to={`/desafios/${i.desafio_id}`} className="font-medium text-indigo-700 underline">
                            {i.desafio}
                          </Link>
                          <span className="block text-xs text-slate-500">
                            {i.concepto} · {i.dificultad}
                          </span>
                        </td>
                        <td className="px-4 py-2 text-slate-700">{i.numero}</td>
                        <td className="px-4 py-2">
                          <span
                            className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                              i.correcto ? "bg-green-100 text-green-900" : "bg-slate-100 text-slate-800"
                            }`}
                          >
                            {i.correcto ? "✓ " : "✗ "}
                            {i.resultado}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {datos.paginas > 1 && (
                <nav aria-label="Paginación del historial" className="mt-3 flex items-center justify-between gap-3">
                  <button
                    type="button"
                    onClick={() => setPagina((p) => Math.max(1, p - 1))}
                    disabled={datos.pagina <= 1 || cargando}
                    className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    ← Anterior
                  </button>
                  <span className="text-sm text-slate-600">
                    Página {datos.pagina} de {datos.paginas}
                  </span>
                  <button
                    type="button"
                    onClick={() => setPagina((p) => Math.min(datos.paginas, p + 1))}
                    disabled={datos.pagina >= datos.paginas || cargando}
                    className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Siguiente →
                  </button>
                </nav>
              )}
            </>
          )}
        </EstadoContenedor>
      </div>
    </section>
  );
}
