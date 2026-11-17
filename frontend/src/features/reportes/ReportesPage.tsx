import { ReactNode, useCallback, useState } from "react";

import { descargarExportacion, obtenerReporte } from "../../api/reportes";
import { mensajeDe } from "../../api/cliente";
import type { Reporte, Suprimible, TipoExportacion } from "../../api/tiposReportes";
import { useCarga } from "../../api/useCarga";
import EstadoContenedor from "../../components/EstadoContenedor";
import { mostrarToast } from "../../components/Toasts";
import FiltroFechas from "../progreso/FiltroFechas";
import { formatearNumero, formatearPorcentaje, rangoInvertido } from "../progreso/fechas";

const EXPORTACIONES: { tipo: TipoExportacion; etiqueta: string }[] = [
  { tipo: "intentos", etiqueta: "Intentos" },
  { tipo: "ayudas", etiqueta: "Ayudas" },
  { tipo: "cambios_ns", etiqueta: "Cambios de NS" },
  { tipo: "indicadores", etiqueta: "Indicadores" },
  { tipo: "todos", etiqueta: "Todo (ZIP)" },
];
const ETIQUETA_CAMBIO: Record<string, string> = { retiro: "Retiro", refuerzo: "Refuerzo", recaida: "Recaída (R3)", otro: "Otro" };

/** Celda de una tabla: un grupo pequeño se muestra como «Oculto», nunca como cero. */
function Celda({ fila, children }: { fila: Suprimible; children: ReactNode }) {
  if (fila.suprimido) return <td className="px-3 py-2 text-slate-400" title="Grupo con pocos estudiantes: no se muestra">Oculto</td>;
  return <td className="px-3 py-2">{children}</td>;
}

function Barra({ valor }: { valor: number | null }) {
  const pct = Math.max(0, Math.min(1, valor ?? 0)) * 100;
  return (
    <div className="flex items-center gap-2">
      <div className="h-2 w-24 overflow-hidden rounded bg-slate-200" aria-hidden="true">
        <div className="h-full bg-indigo-500" style={{ width: `${pct}%` }} />
      </div>
      <span>{formatearPorcentaje(valor)}</span>
    </div>
  );
}

function Tabla({ titulo, columnas, vacio, children }: { titulo: string; columnas: string[]; vacio: boolean; children: ReactNode }) {
  return (
    <section aria-label={titulo} className="space-y-2">
      <h2 className="text-lg font-semibold text-slate-900">{titulo}</h2>
      {vacio ? (
        <p className="rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500">Sin datos en este periodo.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="min-w-full text-left text-sm">
            <caption className="sr-only">{titulo}</caption>
            <thead className="bg-slate-50 text-xs uppercase text-slate-600">
              <tr>
                {columnas.map((c) => (
                  <th key={c} scope="col" className="px-3 py-2">{c}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">{children}</tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function Tarjeta({ titulo, valor, detalle }: { titulo: string; valor: string; detalle?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-sm font-medium text-slate-600">{titulo}</p>
      <p className="mt-1 text-2xl font-bold text-slate-900">{valor}</p>
      {detalle && <p className="mt-1 text-xs text-slate-500">{detalle}</p>}
    </div>
  );
}

function Contenido({ r }: { r: Reporte }) {
  const nombre = (codigo: string) => r.conceptos.find((c) => c.codigo === codigo)?.nombre ?? codigo;
  const e = r.eficacia;
  const num = (s: boolean, v: number | null, d = 0) => (s ? "Oculto" : formatearNumero(v, d));
  return (
    <div className="space-y-8">
      <p role="note" className="rounded-xl border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-900">{r.nota_privacidad}</p>

      <section aria-label="Resumen" className="grid gap-3 sm:grid-cols-3">
        <Tarjeta titulo="Estudiantes activos" valor={r.resumen.suprimido ? "Oculto" : formatearNumero(r.resumen.estudiantes_activos, 0)} detalle="Con al menos una sesión en el periodo" />
        <Tarjeta titulo="m medio de la línea base" valor={r.linea_base.suprimido ? "Oculto" : formatearNumero(r.linea_base.m_global_media)} detalle={r.linea_base.suprimido ? undefined : `${r.linea_base.n_estudiantes ?? 0} estudiantes`} />
        <Tarjeta titulo="Precisión del NS inicial" valor={e.precision_ns_inicial.suprimido ? "Oculto" : formatearPorcentaje(e.precision_ns_inicial.proporcion_coincide)} detalle="Conceptos donde el NS inicial coincidió con el desempeño" />
      </section>

      <Tabla titulo="Uso por semana" columnas={["Semana (lunes)", "Estudiantes activos", "Sesiones", "Intentos"]} vacio={r.uso.length === 0}>
        {r.uso.map((f) => (
          <tr key={f.semana}>
            <th scope="row" className="px-3 py-2 font-medium">{f.semana}</th>
            <Celda fila={f}>{f.estudiantes_activos}</Celda><Celda fila={f}>{f.sesiones}</Celda><Celda fila={f}>{f.intentos}</Celda>
          </tr>
        ))}
      </Tabla>

      <Tabla titulo="Desempeño por concepto y dificultad" columnas={["Concepto", "Dif.", "Estudiantes", "Desafíos", "SA", "CP", "CE", "NR", "Intentos medios", "TR (mediana)"]} vacio={r.desempeno.length === 0}>
        {r.desempeno.map((f) => (
          <tr key={`${f.concepto}-${f.dificultad}`}>
            <th scope="row" className="px-3 py-2 font-medium">{nombre(f.concepto)}</th>
            <td className="px-3 py-2">{f.dificultad}</td>
            <Celda fila={f}>{f.n_estudiantes}</Celda><Celda fila={f}>{f.n_desafios}</Celda>
            <Celda fila={f}><Barra valor={f.tasa_sa} /></Celda>
            <Celda fila={f}>{formatearPorcentaje(f.tasa_cp)}</Celda><Celda fila={f}>{formatearPorcentaje(f.tasa_ce)}</Celda><Celda fila={f}>{formatearPorcentaje(f.tasa_nr)}</Celda>
            <Celda fila={f}>{formatearNumero(f.intentos_medios)}</Celda><Celda fila={f}>{formatearNumero(f.tr_mediana)}</Celda>
          </tr>
        ))}
      </Tabla>

      <Tabla titulo="Distribución del nivel de ayuda (NS) por concepto" columnas={["Concepto", "Estudiantes", "NS 0", "NS 1", "NS 2", "NS 3"]} vacio={r.distribucion_ns.length === 0}>
        {r.distribucion_ns.map((f) => (
          <tr key={f.concepto}>
            <th scope="row" className="px-3 py-2 font-medium">{nombre(f.concepto)}</th>
            <Celda fila={f}>{f.n_estudiantes}</Celda><Celda fila={f}>{f.ns0}</Celda><Celda fila={f}>{f.ns1}</Celda><Celda fila={f}>{f.ns2}</Celda><Celda fila={f}>{f.ns3}</Celda>
          </tr>
        ))}
      </Tabla>

      <Tabla titulo="Ayudas por tipo y valoraciones" columnas={["Tipo", "Solicitudes", "Estudiantes", "Mostradas solas", "Útiles", "No útiles", "% útil"]} vacio={false}>
        {r.ayudas.map((f) => (
          <tr key={f.tipo}>
            <th scope="row" className="px-3 py-2 font-medium">{f.tipo}</th>
            <Celda fila={f}>{f.n_solicitudes}</Celda><Celda fila={f}>{f.n_estudiantes}</Celda><Celda fila={f}>{f.n_mostradas_solas}</Celda>
            <Celda fila={f}>{f.utiles}</Celda><Celda fila={f}>{f.no_utiles}</Celda><Celda fila={f}><Barra valor={f.proporcion_util} /></Celda>
          </tr>
        ))}
      </Tabla>

      <Tabla titulo="Retiros y refuerzos" columnas={["Concepto", "Tipo", "Cambios", "Estudiantes", "Reglas"]} vacio={r.retiros_refuerzos.length === 0}>
        {r.retiros_refuerzos.map((f) => (
          <tr key={`${f.concepto}-${f.tipo}`}>
            <th scope="row" className="px-3 py-2 font-medium">{nombre(f.concepto)}</th>
            <td className="px-3 py-2">{ETIQUETA_CAMBIO[f.tipo]}</td>
            <Celda fila={f}>{f.n_cambios}</Celda><Celda fila={f}>{f.n_estudiantes}</Celda>
            <Celda fila={f}>{Object.entries(f.reglas ?? {}).map(([k, v]) => `${k}: ${v}`).join(" · ")}</Celda>
          </tr>
        ))}
      </Tabla>

      <section aria-labelledby="titulo-eficacia" className="space-y-4">
        <h2 id="titulo-eficacia" className="text-lg font-semibold text-slate-900">¿Funciona el retiro de la ayuda?</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Tarjeta titulo="Conceptos en NS 0 sin recaída" valor={e.ns0_sin_recaida.suprimido ? "Oculto" : e.ns0_sin_recaida.n_conceptos ? formatearPorcentaje(e.ns0_sin_recaida.proporcion) : "—"} detalle={e.ns0_sin_recaida.suprimido || !e.ns0_sin_recaida.n_conceptos ? undefined : `${e.ns0_sin_recaida.sin_recaida} de ${e.ns0_sin_recaida.n_conceptos} conceptos`} />
          <Tarjeta titulo="Desafíos hasta el primer retiro" valor={num(e.desafios_hasta_primer_retiro.global.suprimido, e.desafios_hasta_primer_retiro.global.mediana, 1)} detalle="Mediana por concepto" />
          {e.activacion_r9_r10.map((f) => (
            <Tarjeta key={f.regla} titulo={f.regla === "R9" ? "Activación de R9 (dependencia)" : "Activación de R10 (ensayo y error)"} valor={num(f.suprimido, f.n_activaciones)} detalle={f.suprimido ? undefined : `${f.n_estudiantes} estudiantes · ${formatearPorcentaje(f.proporcion_sesiones)} de las sesiones`} />
          ))}
        </div>
        <Tabla titulo="Proporción de SA a lo largo de los desafíos del estudiante" columnas={["Desafíos n.º", "Estudiantes", "Desafíos", "SA"]} vacio={e.sa_por_bloque.length === 0}>
          {e.sa_por_bloque.map((f) => (
            <tr key={f.desde_orden}>
              <th scope="row" className="px-3 py-2 font-medium">{f.desde_orden}–{f.hasta_orden}</th>
              <Celda fila={f}>{f.n_estudiantes}</Celda><Celda fila={f}>{f.n_desafios}</Celda><Celda fila={f}><Barra valor={f.proporcion_sa} /></Celda>
            </tr>
          ))}
        </Tabla>
        {e.desafios_hasta_primer_retiro.por_concepto.length > 0 && (
          <Tabla titulo="Desafíos hasta el primer retiro, por concepto" columnas={["Concepto", "Conceptos con retiro", "Media", "Mediana", "Mín.", "Máx."]} vacio={false}>
            {e.desafios_hasta_primer_retiro.por_concepto.map((f) => (
              <tr key={f.concepto}>
                <th scope="row" className="px-3 py-2 font-medium">{nombre(f.concepto)}</th>
                <Celda fila={f}>{f.n_conceptos}</Celda><Celda fila={f}>{formatearNumero(f.media, 1)}</Celda><Celda fila={f}>{formatearNumero(f.mediana, 1)}</Celda><Celda fila={f}>{formatearNumero(f.minimo, 0)}</Celda><Celda fila={f}>{formatearNumero(f.maximo, 0)}</Celda>
              </tr>
            ))}
          </Tabla>
        )}
        {!e.precision_ns_inicial.suprimido && (e.precision_ns_inicial.n_conceptos ?? 0) > 0 && (
          <p className="text-sm text-slate-700">
            NS inicial: coincide en {e.precision_ns_inicial.coincide}, era demasiado alto en {e.precision_ns_inicial.inicial_alto} y demasiado bajo en {e.precision_ns_inicial.inicial_bajo} de {e.precision_ns_inicial.n_conceptos} conceptos evaluados.
          </p>
        )}
      </section>
    </div>
  );
}

export default function ReportesPage() {
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [bajando, setBajando] = useState<TipoExportacion | null>(null);
  const invalido = rangoInvertido(desde, hasta);
  const cargador = useCallback(() => obtenerReporte({ desde: desde || undefined, hasta: hasta || undefined }), [desde, hasta]);
  const { datos, cargando, error, recargar } = useCarga(invalido ? () => Promise.resolve(null) : cargador);

  const exportar = async (tipo: TipoExportacion) => {
    setBajando(tipo);
    try {
      await descargarExportacion(tipo, { desde: desde || undefined, hasta: hasta || undefined });
    } catch (e) {
      mostrarToast({ id: "exportar", tipo: "error", mensaje: mensajeDe(e) });
    } finally {
      setBajando(null);
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-slate-900">Reportes</h1>
        <p className="mt-1 text-sm text-slate-600">Uso y desempeño agregados, con seudónimos. Nunca se muestran nombres ni correos.</p>
      </header>

      <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-4">
        <FiltroFechas desde={desde} hasta={hasta} onCambio={(d, h) => { setDesde(d); setHasta(h); }} />
      </div>

      <section aria-labelledby="titulo-exportar" className="space-y-2 rounded-xl border border-slate-200 bg-white p-4">
        <h2 id="titulo-exportar" className="text-base font-semibold text-slate-900">Descargar datos seudonimizados (CSV)</h2>
        <p className="text-sm text-slate-600">Una fila por intento, ayuda, cambio de NS o indicador, con el periodo elegido. Sin datos personales.</p>
        <div className="flex flex-wrap gap-2">
          {EXPORTACIONES.map((x) => (
            <button key={x.tipo} type="button" disabled={invalido || bajando !== null} onClick={() => void exportar(x.tipo)}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60">
              {bajando === x.tipo ? "Descargando…" : x.etiqueta}
            </button>
          ))}
        </div>
      </section>

      <EstadoContenedor cargando={cargando && !invalido} error={invalido ? null : error} vacio={invalido || !datos} mensajeVacio="Corrige el rango de fechas para ver el reporte." onReintentar={() => void recargar()}>
        {datos && <Contenido r={datos} />}
      </EstadoContenedor>
    </div>
  );
}
