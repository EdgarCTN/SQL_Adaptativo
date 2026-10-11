import { Outlet } from "react-router-dom";

import { ToastProvider } from "../components/Toasts";
import { AuthProvider } from "./AuthContext";

/** Ruta raíz: da acceso a la sesión y a los avisos en todas las pantallas. */
export default function Raiz() {
  return (
    <AuthProvider>
      <Outlet />
      <ToastProvider />
    </AuthProvider>
  );
}
