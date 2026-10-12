import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";

import type { Rol } from "../api/tipos";
import ErrorBoundary from "../components/ErrorBoundary";
import { useAuth } from "./AuthContext";

// Solo rutas que existan y funcionen.
const ENLACES: { a: string; etiqueta: string; roles?: Rol[] }[] = [
  { a: "/desafios", etiqueta: "Desafíos", roles: ["estudiante"] },
  { a: "/progreso", etiqueta: "Progreso", roles: ["estudiante"] },
  { a: "/perfil", etiqueta: "Perfil" },
];

export default function Layout() {
  const { usuario, logout } = useAuth();
  const ubicacion = useLocation();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [saliendo, setSaliendo] = useState(false);

  useEffect(() => setMenuAbierto(false), [ubicacion.pathname]);

  const salir = async () => {
    setSaliendo(true);
    await logout();
  };

  const clasesEnlace = ({ isActive }: { isActive: boolean }) =>
    `block rounded-lg px-3 py-2 text-sm font-medium ${
      isActive ? "bg-indigo-100 text-indigo-800" : "text-slate-700 hover:bg-slate-100"
    }`;

  return (
    <div className="min-h-screen md:flex">
      <aside
        className={`${menuAbierto ? "block" : "hidden"} border-b border-slate-200 bg-white p-4 md:block md:w-56 md:shrink-0 md:border-b-0 md:border-r`}
      >
        <p className="mb-4 hidden text-lg font-bold text-indigo-700 md:block">Desafíos SQL</p>
        <nav aria-label="Principal" className="space-y-1">
          {ENLACES.filter((e) => !e.roles || (usuario && e.roles.includes(usuario.rol))).map((e) => (
            <NavLink key={e.a} to={e.a} className={clasesEnlace}>
              {e.etiqueta}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3">
          <button
            type="button"
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm md:hidden"
            aria-expanded={menuAbierto}
            onClick={() => setMenuAbierto((v) => !v)}
          >
            Menú
          </button>
          <p className="text-lg font-bold text-indigo-700 md:hidden">Desafíos SQL</p>
          <div className="ml-auto flex items-center gap-3">
            <span className="max-w-[10rem] truncate text-sm text-slate-700 sm:max-w-xs">{usuario?.nombre}</span>
            <button
              type="button"
              onClick={() => void salir()}
              disabled={saliendo}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
            >
              {saliendo ? "Saliendo…" : "Cerrar sesión"}
            </button>
          </div>
        </header>
        <main className="flex-1 p-4 sm:p-6">
          {usuario?.rol === "estudiante" && !usuario.linea_base_completada && (
            <div role="status" className="mb-4 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
              <strong>Diagnóstico pendiente.</strong> Complétalo para ajustar la dificultad y la ayuda a tu nivel.{" "}
              <Link to="/consentimiento" className="font-semibold underline">
                Completar ahora
              </Link>
            </div>
          )}
          <ErrorBoundary key={ubicacion.pathname}>
            <Outlet />
          </ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
