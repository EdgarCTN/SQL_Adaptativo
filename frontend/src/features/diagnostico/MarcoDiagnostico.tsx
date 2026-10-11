import { ReactNode, useState } from "react";

import { useAuth } from "../../app/AuthContext";

/** Marco simple (sin menú) para las pantallas de consentimiento y diagnóstico. */
export default function MarcoDiagnostico({ children }: { children: ReactNode }) {
  const { usuario, logout } = useAuth();
  const [saliendo, setSaliendo] = useState(false);

  return (
    <div className="min-h-screen">
      <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3">
        <p className="text-lg font-bold text-indigo-700">Desafíos SQL</p>
        <div className="ml-auto flex items-center gap-3">
          <span className="max-w-[10rem] truncate text-sm text-slate-700 sm:max-w-xs">{usuario?.nombre}</span>
          <button
            type="button"
            disabled={saliendo}
            onClick={() => {
              setSaliendo(true);
              void logout();
            }}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          >
            {saliendo ? "Saliendo…" : "Cerrar sesión"}
          </button>
        </div>
      </header>
      <main className="mx-auto w-full max-w-3xl p-4 sm:p-6">{children}</main>
    </div>
  );
}
