import { useState } from "react";
import { Link } from "react-router-dom";

import NotificacionFila from "./NotificacionFila";
import { useNotificaciones } from "./NotificacionesContext";

export default function CampanaNotificaciones() {
  const [abierta, setAbierta] = useState(false);
  const { notificaciones, noLeidas, cargando, error, ocupadoId, recargar, marcarLeida, marcarTodas, responder } = useNotificaciones();
  const recientes = notificaciones.slice(0, 5);

  return (
    <div className="relative">
      <button type="button" aria-label={`Notificaciones${noLeidas ? `, ${noLeidas} sin leer` : ""}`}
        aria-expanded={abierta} aria-controls="panel-notificaciones" onClick={() => setAbierta((v) => !v)}
        className="relative rounded-lg border border-slate-300 p-2 text-slate-700 hover:bg-slate-50">
        <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path strokeLinecap="round" strokeLinejoin="round" d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" />
        </svg>
        {noLeidas > 0 && <span className="absolute -right-2 -top-2 min-w-5 rounded-full bg-red-600 px-1 text-center text-xs font-bold leading-5 text-white">{noLeidas > 99 ? "99+" : noLeidas}</span>}
      </button>
      {abierta && (
        <section id="panel-notificaciones" aria-label="Notificaciones recientes" className="absolute right-0 z-30 mt-2 w-[min(92vw,26rem)] rounded-xl border border-slate-200 bg-white p-3 shadow-xl">
          <header className="flex items-center justify-between gap-2 border-b border-slate-100 pb-2">
            <h2 className="font-semibold text-slate-900">Notificaciones</h2>
            {noLeidas > 0 && <button type="button" onClick={() => void marcarTodas()} className="text-xs font-semibold text-indigo-700 underline">Leer todas</button>}
          </header>
          <div className="max-h-[65vh] space-y-2 overflow-y-auto py-2" aria-live="polite">
            {cargando && <p role="status" className="p-4 text-center text-sm text-slate-600">Cargando notificaciones…</p>}
            {!cargando && error && <div role="alert" className="p-4 text-center text-sm text-red-700">{error}<button type="button" onClick={recargar} className="ml-2 font-semibold underline">Reintentar</button></div>}
            {!cargando && !error && recientes.length === 0 && <p className="p-4 text-center text-sm text-slate-600">No tienes notificaciones.</p>}
            {!cargando && !error && recientes.map((n) => <NotificacionFila key={n.id} notificacion={n} ocupado={ocupadoId === n.id} onMarcarLeida={(id) => void marcarLeida(id)} onResponder={(item, accion) => void responder(item, accion)} />)}
          </div>
          <Link to="/notificaciones" onClick={() => setAbierta(false)} className="block border-t border-slate-100 pt-2 text-center text-sm font-semibold text-indigo-700 hover:underline">Ver todas</Link>
        </section>
      )}
    </div>
  );
}
