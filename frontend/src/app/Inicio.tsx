import { Navigate } from "react-router-dom";

import { useAuth } from "./AuthContext";
import { destinoTrasLogin } from "./destinos";

/** Ruta «/»: lleva a cada usuario a su pantalla de inicio (va dentro de RutaProtegida). */
export default function Inicio() {
  const { usuario } = useAuth();
  return <Navigate to={usuario ? destinoTrasLogin(usuario) : "/login"} replace />;
}
