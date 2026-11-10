import type { Notificacion } from "../../api/notificaciones";

const TITULOS: Record<string, string> = {
  retiro: "Menos ayuda",
  refuerzo: "Más apoyo",
  verificacion: "Desafío de verificación",
  sugerencia: "Práctica sugerida",
  estancamiento: "Siguiente paso",
  recaida: "Recuperamos apoyo",
  cambio_dificultad: "Cambio de dificultad",
  reenganche: "Bienvenido/a de vuelta",
  retiro_aviso: "Aviso sobre tu ayuda",
  retiro_pregunta: "Decisión sobre tu ayuda",
  reflexion: "Pausa de reflexión",
  sobreconfianza: "Revisa tu solución",
};

interface Props {
  notificacion: Notificacion;
  ocupado: boolean;
  onMarcarLeida: (id: number) => void;
  onResponder: (notificacion: Notificacion, accion: "aceptar" | "mantener") => void;
}

export default function NotificacionFila({ notificacion, ocupado, onMarcarLeida, onResponder }: Props) {
  const esAviso = notificacion.tipo === "retiro_aviso" && notificacion.ajuste_id !== null;
  const esPregunta = notificacion.tipo === "retiro_pregunta" && notificacion.ajuste_id !== null;
  const fecha = new Date(notificacion.creada_en).toLocaleString("es");

  return (
    <article className={`rounded-xl border p-4 ${notificacion.leida ? "border-slate-200 bg-white" : "border-indigo-200 bg-indigo-50"}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-indigo-800">
            {TITULOS[notificacion.tipo] ?? notificacion.tipo.replace(/_/g, " ")}{notificacion.regla ? ` · ${notificacion.regla}` : ""}
          </p>
          <p className="mt-1 text-sm text-slate-800">{notificacion.texto}</p>
          <time className="mt-2 block text-xs text-slate-500" dateTime={notificacion.creada_en}>{fecha}</time>
        </div>
        {!notificacion.leida && !esAviso && !esPregunta && (
          <button type="button" onClick={() => onMarcarLeida(notificacion.id)} className="shrink-0 text-xs font-semibold text-indigo-700 underline">
            Marcar leída
          </button>
        )}
      </div>
      {esAviso && (
        <button type="button" disabled={ocupado} onClick={() => onResponder(notificacion, "mantener")}
          className="mt-3 rounded-lg border border-indigo-300 bg-white px-3 py-1.5 text-sm font-semibold text-indigo-800 disabled:opacity-60">
          {ocupado ? "Guardando…" : "Mantener la ayuda"}
        </button>
      )}
      {esPregunta && (
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" disabled={ocupado} onClick={() => onResponder(notificacion, "aceptar")}
            className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-60">
            Ofrecer menos ayuda
          </button>
          <button type="button" disabled={ocupado} onClick={() => onResponder(notificacion, "mantener")}
            className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 disabled:opacity-60">
            Mantener el nivel
          </button>
        </div>
      )}
    </article>
  );
}
