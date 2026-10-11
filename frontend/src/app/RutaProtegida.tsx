import { Navigate, Outlet, useLocation } from "react-router-dom";

import type { Rol } from "../api/tipos";
import { useAuth } from "./AuthContext";
import { destinoTrasLogin } from "./destinos";

function Cargando() {
  return (
    <div role="status" className="flex min-h-screen items-center justify-center gap-3 text-slate-500">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-indigo-500 border-t-transparent" />
      Cargando…
    </div>
  );
}

/** Exige sesión y, si se indican `roles`, que el usuario tenga uno de ellos. */
export function RutaProtegida({ roles }: { roles?: Rol[] }) {
  const { usuario, cargando } = useAuth();
  const ubicacion = useLocation();

  if (cargando) return <Cargando />;
  if (!usuario) return <Navigate to="/login" replace state={{ desde: ubicacion.pathname }} />;
  if (roles && !roles.includes(usuario.rol)) return <Navigate to="/403" replace />;
  return <Outlet />;
}

/** Páginas solo para visitantes (login, registro): si ya hay sesión, redirige. */
export function RutaPublica() {
  const { usuario, cargando } = useAuth();
  if (cargando) return <Cargando />;
  if (usuario) return <Navigate to={destinoTrasLogin(usuario)} replace />;
  return <Outlet />;
}
