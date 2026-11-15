import { useCallback, useId, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { obtenerEvolucion } from "../../api/progreso";
import type { CambioNs, Evolucion, PuntoIndicadores } from "../../api/tiposProgreso";
import { useCarga } from "../../api/useCarga";
import EstadoContenedor from "../../components/EstadoContenedor";
import FiltroFechas from "./FiltroFechas";
import GraficoSerie, { type FilaGrafico } from "./GraficoSerie";
import {
  finDelDia,
  formatearFechaCorta,
  formatearFechaHora,
  formatearNumero,
  formatearPorcentaje,
  inicioDelDia,
  rangoInvertido,
} from "./fechas";

const MSG_SIN_HISTORIAL = "Todavía no tienes historial. Tus indicadores aparecerán aquí cuando cierres tu primer desafío.";

function resumir(valores: (number | null)[], formato: (v: number) => string): string {
  const v = valores.filter((x): x is number => x !== null);
  const cierres = `${valores.length} ${valores.length === 1 ? "cierre" : "cierres"}.`;
  if (v.length === 0) return `${cierres} Sin datos para este indicador.`;
  if (v.length === 1) return `${cierres} Valor: ${formato(v[0])}.`;
  return `${cierres} Primer valor: ${formato(v[0])}; último: ${formato(v[v.length - 1])}; mínimo: ${formato(Math.min(...v))}; máximo: ${formato(Math.max(...v))}.`;
}

function filasDe(puntos: PuntoIndicadores[], clave: "ta" | "ni" | "tr" | "ua"): FilaGrafico[] {
  return puntos.map((p, i) => ({
    etiqueta: String(i + 1),
    detalle: `Cierre ${i + 1} · ${formatearFechaHora(p.fecha)}`,
    valor: p[clave],
  }));
}

function filasNs(cambios: CambioNs[]): FilaGrafico[] {
  if (cambios.length === 0) return [];
  return [
    { etiqueta: "Inicio", detalle: "Antes del primer cambio", valor: cambios[0].ns_anterior },
    ...cambios.map((c, i) => ({
      etiqueta: String(i + 1),
      detalle: `${formatearFechaHora(c.fecha)} · ${c.concepto_nombre}`,
      valor: c.ns_nuevo,
    })),
  ];
}

const TH = "px-4 py-2 font-medium";

function Graficos({ puntos, cambios, nombre }: { puntos: PuntoIndicadores[]; cambios: CambioNs[]; nombre: string }) {
  if (puntos.length === 0 && cambios.length === 0) {
    return (
      <p role="status" className="rounded-xl border border-dashed border-slate-300 p-6 text-center text-sm text-slate-600">
        No hay registros de «{nombre}» en este rango de fechas. Prueba con otro rango o quita las fechas.
      </p>
    );
  }
  const porcentaje = formatearPorcentaje;
  const decimal = (v: number) => formatearNumero(v, 1);
  const veces = (v: number) => `${formatearNumero(v, 2)}×`;
  const nsActual = puntos.length > 0 ? puntos[puntos.length - 1].ns : cambios[cambios.length - 1]?.ns_nuevo;
  const ns = filasNs(cambios);

  return (
    <div className="space-y-4">
      <p className="text-sm text-slate-600">
        Cada punto es un desafío de «{nombre}» que cerraste. Los indicadores se calculan con tus últimos 5 desafíos de ese concepto
        desde el último cambio de nivel.
      </p>

      <div className="grid gap-4 md:grid-cols-2">
        <GraficoSerie
          titulo="Acierto"
          descripcion="Proporción de desafíos resueltos sin ayuda o con la ayuda prevista para tu nivel."
          filas={filasDe(puntos, "ta")}
          alternativa={resumir(puntos.map((p) => p.ta), porcentaje)}
          formato={porcentaje}
          dominio={[0, 1]}
          ticks={[0, 0.25, 0.5, 0.75, 1]}
          etiquetaX="Cierre n.º"
        />
        <GraficoSerie
          titulo="Uso de ayuda"
          descripcion="Proporción de desafíos en los que pediste o aceptaste ayuda."
          filas={filasDe(puntos, "ua")}
          alternativa={resumir(puntos.map((p) => p.ua), porcentaje)}
          formato={porcentaje}
          dominio={[0, 1]}
          ticks={[0, 0.25, 0.5, 0.75, 1]}
          etiquetaX="Cierre n.º"
        />
        <GraficoSerie
          titulo="Envíos por desafío"
          descripcion="Cantidad típica (mediana) de envíos que necesitas en cada desafío."
          filas={filasDe(puntos, "ni")}
          alternativa={resumir(puntos.map((p) => p.ni), decimal)}
          formato={decimal}
          etiquetaX="Cierre n.º"
        />
        <GraficoSerie
          titulo="Tiempo frente a la referencia"
          descripcion="Tu tiempo activo dividido entre el tiempo de referencia del desafío; 1× es igual al de referencia."
          filas={filasDe(puntos, "tr")}
          alternativa={resumir(puntos.map((p) => p.tr), veces)}
          formato={veces}
          lineaReferencia={{ y: 1, etiqueta: "Referencia" }}
          etiquetaX="Cierre n.º"
        />
      </div>

      <details className="rounded-xl border border-slate-200 bg-white">
        <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-slate-800">
          Ver los datos de los gráficos en una tabla
        </summary>
        <div className="overflow-x-auto border-t border-slate-100">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Indicadores y nivel de ayuda después de cada desafío cerrado de {nombre}</caption>
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th scope="col" className={TH}>Cierre</th>
                <th scope="col" className={TH}>Fecha</th>
                <th scope="col" className={TH}>Nivel (NS)</th>
                <th scope="col" className={TH}>Acierto</th>
                <th scope="col" className={TH}>Uso de ayuda</th>
                <th scope="col" className={TH}>Envíos</th>
                <th scope="col" className={TH}>Tiempo</th>
              </tr>
            </thead>
            <tbody>
              {puntos.map((p, i) => (
                <tr key={p.sesion_id} className="border-t border-slate-100">
                  <td className="px-4 py-2 text-slate-700">{i + 1}</td>
                  <td className="whitespace-nowrap px-4 py-2 text-slate-700">{formatearFechaHora(p.fecha)}</td>
                  <td className="px-4 py-2 text-slate-700">{p.ns}</td>
                  <td className="px-4 py-2 text-slate-700">{porcentaje(p.ta)}</td>
                  <td className="px-4 py-2 text-slate-700">{porcentaje(p.ua)}</td>
                  <td className="px-4 py-2 text-slate-700">{formatearNumero(p.ni, 1)}</td>
                  <td className="px-4 py-2 text-slate-700">{p.tr === null ? "—" : veces(p.tr)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <section aria-labelledby="titulo-linea-ns" className="space-y-3">
        <h3 id="titulo-linea-ns" className="text-base font-semibold text-slate-900">
          Línea de tiempo de tu nivel de ayuda
        </h3>
        {cambios.length === 0 ? (
          <p role="status" className="rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-600">
            Tu nivel de ayuda en «{nombre}» no cambió en este periodo
            {nsActual !== undefined ? ` y está en NS ${nsActual}` : ""}.
          </p>
        ) : (
          <>
            <GraficoSerie
              titulo="Nivel de ayuda (NS)"
              descripcion="De 0 a 3: mientras más alto, más apoyo recibes en este tema."
              filas={ns}
              alternativa={`Empezaste este periodo en NS ${cambios[0].ns_anterior}, tuviste ${cambios.length} ${
                cambios.length === 1 ? "cambio" : "cambios"
              } y ahora estás en NS ${cambios[cambios.length - 1].ns_nuevo}. El detalle está en la tabla de abajo.`}
              formato={(v) => `NS ${v}`}
              dominio={[0, 3]}
              ticks={[0, 1, 2, 3]}
              escalon
              etiquetaX="Cambio n.º"
            />
            <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Cambios de nivel de ayuda en {nombre}</caption>
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th scope="col" className={TH}>Fecha</th>
                    <th scope="col" className={TH}>Cambio</th>
                    <th scope="col" className={TH}>Motivo</th>
                  </tr>
                </thead>
                <tbody>
                  {cambios.map((c, i) => (
                    <tr key={`${c.fecha}-${i}`} className="border-t border-slate-100 align-top">
                      <td className="whitespace-nowrap px-4 py-2 text-slate-700">{formatearFechaCorta(c.fecha)}</td>
                      <td className="whitespace-nowrap px-4 py-2 text-slate-700">
                        {c.ns_anterior} → {c.ns_nuevo} {c.ns_nuevo < c.ns_anterior ? "(menos ayuda)" : "(más apoyo)"}
                      </td>
                      <td className="px-4 py-2 text-slate-700">{c.texto}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </div>
  );
}

function elegirConcepto(datos: Evolucion | null, elegido: string): string {
  if (!datos) return "";
  if (elegido) return elegido;
  const ultimoPunto = datos.indicadores[datos.indicadores.length - 1];
  const ultimoCambio = datos.cambios_ns[datos.cambios_ns.length - 1];
  return ultimoPunto?.concepto ?? ultimoCambio?.concepto ?? datos.conceptos_con_datos[0]?.codigo ?? "";
}

export default function EvolucionProgreso() {
  const id = useId();
  const [concepto, setConcepto] = useState(""); // vacío = el concepto con actividad más reciente
  const [entrada, setEntrada] = useState({ desde: "", hasta: "" });
  const [aplicado, setAplicado] = useState({ desde: "", hasta: "" });

  const cargador = useCallback(
    () =>
      obtenerEvolucion({
        concepto: concepto || undefined,
        desde: inicioDelDia(aplicado.desde),
        hasta: finDelDia(aplicado.hasta),
      }),
    [concepto, aplicado],
  );
  const { datos, cargando, error, recargar } = useCarga(cargador);

  const mostrado = useMemo(() => elegirConcepto(datos, concepto), [datos, concepto]);
  const puntos = useMemo(() => (datos?.indicadores ?? []).filter((p) => p.concepto === mostrado), [datos, mostrado]);
  const cambios = useMemo(() => (datos?.cambios_ns ?? []).filter((c) => c.concepto === mostrado), [datos, mostrado]);
  const opciones = datos?.conceptos_con_datos ?? [];
  const nombre = opciones.find((o) => o.codigo === mostrado)?.nombre ?? mostrado;
  const hayFiltros = Boolean(concepto || entrada.desde || entrada.hasta);

  const alCambiarFechas = (desde: string, hasta: string) => {
    setEntrada({ desde, hasta });
    if (!rangoInvertido(desde, hasta)) setAplicado({ desde, hasta }); // con el rango al revés no se consulta
  };
  const limpiar = () => {
    setConcepto("");
    setEntrada({ desde: "", hasta: "" });
    setAplicado({ desde: "", hasta: "" });
  };

  return (
    <section aria-labelledby={`${id}-titulo`}>
      <h2 id={`${id}-titulo`} className="text-lg font-semibold text-slate-900">
        Evolución de tus indicadores
      </h2>
      <p className="mt-1 text-sm text-slate-600">Cómo han cambiado tu acierto, tu uso de ayuda y tu nivel a lo largo del tiempo.</p>

      {opciones.length > 0 && (
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor={`${id}-concepto`} className="block text-sm font-medium text-slate-700">
              Concepto
            </label>
            <select
              id={`${id}-concepto`}
              value={mostrado}
              onChange={(e) => setConcepto(e.target.value)}
              className="mt-1 block rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
            >
              {opciones.map((o) => (
                <option key={o.codigo} value={o.codigo}>
                  {o.nombre}
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
          vacio={datos !== null && opciones.length === 0}
          mensajeVacio={MSG_SIN_HISTORIAL}
        >
          {datos && opciones.length > 0 && <Graficos puntos={puntos} cambios={cambios} nombre={nombre} />}
        </EstadoContenedor>
        {datos && !error && opciones.length === 0 && (
          <Link to="/desafios" className="mt-2 inline-block text-sm font-semibold text-indigo-700 underline">
            Ir a los desafíos
          </Link>
        )}
      </div>
    </section>
  );
}
