import type { ResultadoIntento as Resultado, TipoResultado } from "../../api/tiposDesafios";
import { formatearDuracion } from "./formatos";
import TablaResultado from "./TablaResultado";

const TITULOS: Record<TipoResultado, string> = {
  correcto: "✓ ¡Correcto!",
  resultado_distinto: "✗ Aún no coincide",
  error_sql: "⚠ Hay un error en tu consulta",
  no_permitida: "⚠ Operación no permitida",
  varias_sentencias: "⚠ Envía una sola sentencia",
  tiempo_agotado: "⚠ La consulta tardó demasiado",
};

const ESTILOS: Record<TipoResultado, string> = {
  correcto: "border-green-300 bg-green-50 text-green-900",
  resultado_distinto: "border-amber-300 bg-amber-50 text-amber-900",
  error_sql: "border-red-300 bg-red-50 text-red-900",
  no_permitida: "border-red-300 bg-red-50 text-red-900",
  varias_sentencias: "border-red-300 bg-red-50 text-red-900",
  tiempo_agotado: "border-red-300 bg-red-50 text-red-900",
};

export default function ResultadoIntento({ intento }: { intento: Resultado }) {
  const tipo = intento.tipo_resultado;
  const hayTabla = tipo === "correcto" || tipo === "resultado_distinto";
  // Correcta pero con la solución completa a la vista (AY4): el desafío queda como no resuelto.
  const correctaNR = intento.desafio_resuelto && intento.resultado_cierre === "NR";
  return (
    <section
      className={`rounded-xl border p-4 ${correctaNR ? "border-amber-300 bg-amber-50 text-amber-900" : (ESTILOS[tipo] ?? ESTILOS.error_sql)}`}
    >
      <p className="text-xs font-medium opacity-80">Intento {intento.numero}</p>
      <h2 className="text-lg font-bold">
        {correctaNR ? "✓ Tu consulta es correcta" : (TITULOS[tipo] ?? "Resultado del intento")}
      </h2>
      <p className="mt-1 text-sm">{intento.mensaje}</p>

      {correctaNR && (
        <p className="mt-2 text-sm font-medium">
          Como viste la solución completa, este desafío queda registrado como no resuelto. Puedes intentarlo de nuevo más adelante.
        </p>
      )}
      {intento.desafio_resuelto && !correctaNR && (
        <p className="mt-2 text-sm font-medium">
          Resolviste el desafío en {intento.numero} {intento.numero === 1 ? "intento" : "intentos"}
          {intento.tiempo_activo_seg !== null && <> y {formatearDuracion(intento.tiempo_activo_seg)}</>}.
        </p>
      )}

      {hayTabla && (
        <details open={tipo === "resultado_distinto"} className="mt-3">
          <summary className="cursor-pointer text-sm font-semibold">
            Tu resultado ({intento.total_filas} {intento.total_filas === 1 ? "fila" : "filas"}
            {intento.truncado ? ", hay más" : ""})
          </summary>
          <TablaResultado columnas={intento.columnas} filas={intento.filas} titulo="Resultado de tu consulta" />
          {intento.truncado && (
            <p className="mt-2 text-xs">Se muestran solo las primeras {intento.total_filas} filas; tu consulta devuelve más.</p>
          )}
        </details>
      )}

      {intento.detalle_tecnico && (
        <details className="mt-3">
          <summary className="cursor-pointer text-sm font-semibold">Ver detalle técnico</summary>
          <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded bg-white/70 p-2 font-mono text-xs text-slate-800">
            {intento.detalle_tecnico}
          </pre>
        </details>
      )}
    </section>
  );
}
