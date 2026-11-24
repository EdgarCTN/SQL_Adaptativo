import { useEffect } from "react";
import { Outlet } from "react-router-dom";

import { calentarServidor, probablementeDormido } from "../api/servidor";
import BannerServidor from "../components/BannerServidor";
import { ToastProvider } from "../components/Toasts";
import { AuthProvider } from "./AuthContext";

/** Ruta raíz: da acceso a la sesión y a los avisos en todas las pantallas. */
export default function Raiz() {
  // Al volver a la pestaña tras un rato, si el servidor pudo dormirse, empieza a despertarlo.
  useEffect(() => {
    const alVolver = () => {
      if (document.visibilityState === "visible" && probablementeDormido()) void calentarServidor();
    };
    document.addEventListener("visibilitychange", alVolver);
    return () => document.removeEventListener("visibilitychange", alVolver);
  }, []);

  return (
    <AuthProvider>
      <BannerServidor />
      <Outlet />
      <ToastProvider />
    </AuthProvider>
  );
}
