import { useId, useState } from "react";

import type { AyudaRecibida, TipoAyuda } from "../../api/tiposDesafios";
import { MAX_MENSAJE_AYUDA } from "./useAyuda";

export const NOMBRE_TIPO: Record<TipoAyuda, string> = {
  AY1: "Pista general",
  AY2: "Ejemplo guiado",
  AY3: "Solución parcial",
  AY4: "Solución completa",
};

interface Props {
  ayudas: AyudaRecibida[];
  activo: boolean; // sesión en curso y desafío aún sin resolver
  pidiendo: boolean;
  deshabilitado: boolean; // p. ej. mientras se envía una consulta
  errorAyuda: string | null;
  avisoSolo: string | null;
  valorando: number | null;
  onPedir: (mensaje: string) => Promise<boolean>;
  onValorar: (solicitudId: number, valor: 1 | -1) => void;
}

function TarjetaAyuda({
  ayuda,
  numero,
  ocupado,
  onValorar,
}: {
  ayuda: AyudaRecibida;
  numero: number;
  ocupado: boolean;
  onValorar: (valor: 1 | -1) => void;
}) {
  return (
    <article className="rounded-xl border border-slate-200 bg-white p-4" aria-label={`Ayuda ${numero}: ${NOMBRE_TIPO[ayuda.tipo_ayuda]}`}>
      <header className="flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-bold text-slate-900">
          Ayuda {numero} · {ayuda.tipo_ayuda} · {NOMBRE_TIPO[ayuda.tipo_ayuda]}
        </h3>
        {ayuda.etiquetas.map((e, i) => (
          <span
            key={i}
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${i === 0 ? "bg-slate-100 text-slate-700" : "bg-amber-100 text-amber-900"}`}
          >
            {e}
          </span>
        ))}
      </header>
      {ayuda.reformulada && <p className="mt-1 text-xs text-slate-500">Es otra forma de explicar la ayuda anterior.</p>}
      <p className="mt-2 whitespace-pre-line text-sm text-slate-800">{ayuda.mensaje}</p>
      {ayuda.codigo_sql && (
        <pre
          aria-label="Código SQL de la ayuda"
          className="mt-2 overflow-x-auto rounded-lg bg-slate-900 p-3 font-mono text-xs text-slate-100"
        >
          {ayuda.codigo_sql}
        </pre>
      )}
      {ayuda.sugerencia && <p className="mt-2 text-sm italic text-slate-600">{ayuda.sugerencia}</p>}
      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-slate-100 pt-2">
        <span className="text-xs text-slate-600">¿Te sirvió esta ayuda?</span>
        {([1, -1] as const).map((v) => (
          <button
            key={v}
            type="button"
            disabled={ocupado}
            aria-pressed={ayuda.valoracion === v}
            aria-label={v === 1 ? "Esta ayuda me sirvió" : "Esta ayuda no me sirvió"}
            onClick={() => onValorar(v)}
            className={`rounded-lg border px-2 py-1 text-xs font-medium disabled:opacity-60 ${
              ayuda.valoracion === v
                ? "border-indigo-500 bg-indigo-50 text-indigo-900"
                : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
            }`}
          >
            <span aria-hidden="true">{v === 1 ? "👍" : "👎"}</span> {v === 1 ? "Útil" : "No útil"}
          </button>
        ))}
        {ayuda.valoracion !== null && <span className="text-xs text-slate-500">Gracias por tu valoración.</span>}
      </div>
    </article>
  );
}

export default function PanelAyuda({
  ayudas,
  activo,
  pidiendo,
  deshabilitado,
  errorAyuda,
  avisoSolo,
  valorando,
  onPedir,
  onValorar,
}: Props) {
  const [mensaje, setMensaje] = useState("");
  const idMensaje = useId();
  const pedir = async () => {
    if (await onPedir(mensaje)) setMensaje("");
  };

  return (
    <section className="mt-6" aria-labelledby="titulo-ayuda">
      <h2 id="titulo-ayuda" className="text-base font-semibold text-slate-900">
        Ayuda
      </h2>

      {activo && (
        <div className="mt-2 rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-sm text-slate-700">Puedes pedir ayuda cuando quieras. Si lo deseas, cuéntanos qué te está costando.</p>
          <label htmlFor={idMensaje} className="mt-2 block text-sm font-medium text-slate-800">
            Mensaje (opcional)
          </label>
          <textarea
            id={idMensaje}
            value={mensaje}
            onChange={(e) => setMensaje(e.target.value)}
            maxLength={MAX_MENSAJE_AYUDA}
            rows={2}
            disabled={pidiendo}
            className="mt-1 w-full rounded-lg border border-slate-300 p-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200"
          />
          <p className="text-right text-xs text-slate-500">
            {mensaje.length}/{MAX_MENSAJE_AYUDA}
          </p>
          <button
            type="button"
            onClick={() => void pedir()}
            disabled={pidiendo || deshabilitado}
            className="mt-1 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
          >
            {pidiendo ? "Buscando ayuda…" : "Pedir ayuda"}
          </button>
        </div>
      )}

      <div aria-live="polite" className="mt-2 space-y-2">
        {errorAyuda && (
          <p role="alert" className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
            {errorAyuda}
          </p>
        )}
        {avisoSolo && (
          <p className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">{avisoSolo}</p>
        )}
      </div>

      {ayudas.length === 0 ? (
        <p className="mt-2 text-sm text-slate-500">Todavía no has pedido ayuda en esta sesión.</p>
      ) : (
        <div className="mt-3 space-y-3">
          {[...ayudas]
            .map((a, i) => ({ a, n: i + 1 }))
            .reverse()
            .map(({ a, n }) => (
              <TarjetaAyuda
                key={a.solicitud_id}
                ayuda={a}
                numero={n}
                ocupado={valorando !== null}
                onValorar={(v) => onValorar(a.solicitud_id, v)}
              />
            ))}
        </div>
      )}
    </section>
  );
}
