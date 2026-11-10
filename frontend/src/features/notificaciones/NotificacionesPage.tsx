import EstadoContenedor from "../../components/EstadoContenedor";
import NotificacionFila from "./NotificacionFila";
import { useNotificaciones } from "./NotificacionesContext";

export default function NotificacionesPage() {
  const { notificaciones, noLeidas, cargando, error, ocupadoId, recargar, marcarLeida, marcarTodas, responder } = useNotificaciones();

  return (
    <section className="mx-auto max-w-3xl">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Notificaciones</h1>
          <p className="mt-1 text-sm text-slate-600">Avisos sobre tus cambios de nivel de ayuda y actividad.</p>
        </div>
        {noLeidas > 0 && <button type="button" onClick={() => void marcarTodas()} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">Marcar todas como leídas</button>}
      </header>
      <EstadoContenedor cargando={cargando} error={error} vacio={!cargando && !error && notificaciones.length === 0} mensajeVacio="Todavía no tienes notificaciones." onReintentar={recargar}>
        <div className="space-y-3">
          {notificaciones.map((n) => <NotificacionFila key={n.id} notificacion={n} ocupado={ocupadoId === n.id} onMarcarLeida={(id) => void marcarLeida(id)} onResponder={(item, accion) => void responder(item, accion)} />)}
        </div>
      </EstadoContenedor>
    </section>
  );
}
