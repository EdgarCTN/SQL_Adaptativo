import { ReactNode } from "react";

interface Props {
  cargando: boolean;
  error?: string | null;
  vacio?: boolean;
  mensajeVacio?: string;
  onReintentar?: () => void;
  children: ReactNode;
}

/** Resuelve los 4 estados de una pantalla: cargando, error, vacío y con datos. */
export default function EstadoContenedor({
  cargando,
  error,
  vacio = false,
  mensajeVacio = "Todavía no hay nada para mostrar aquí.",
  onReintentar,
  children,
}: Props) {
  if (cargando) {
    return (
      <div role="status" className="flex items-center justify-center gap-3 p-10 text-slate-500">
        <span className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
        Cargando…
      </div>
    );
  }
  if (error) {
    return (
      <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-6 text-center">
        <p className="text-sm text-red-800">{error}</p>
        {onReintentar && (
          <button
            type="button"
            onClick={onReintentar}
            className="mt-3 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
          >
            Reintentar
          </button>
        )}
      </div>
    );
  }
  if (vacio) {
    return <p className="rounded-xl border border-dashed border-slate-300 p-10 text-center text-sm text-slate-500">{mensajeVacio}</p>;
  }
  return <>{children}</>;
}
