import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { cerrarSesionApi, iniciarSesion, obtenerYo, registrarCuenta } from "../api/auth";
import { borrarToken, guardarToken, leerToken } from "../api/cliente";
import type { Usuario } from "../api/tipos";

interface AuthValor {
  usuario: Usuario | null;
  cargando: boolean;
  login: (correo: string, contrasena: string) => Promise<Usuario>;
  registrar: (nombre: string, correo: string, contrasena: string) => Promise<Usuario>;
  logout: () => Promise<void>;
  actualizarUsuario: (u: Usuario) => void;
}

const AuthContext = createContext<AuthValor | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargando, setCargando] = useState<boolean>(() => leerToken() !== null);

  // Al abrir la app, recupera la sesión si hay token guardado.
  useEffect(() => {
    if (!leerToken()) return;
    let activo = true;
    obtenerYo()
      .then((u) => activo && setUsuario(u))
      .catch(() => activo && setUsuario(null))
      .finally(() => activo && setCargando(false));
    return () => {
      activo = false;
    };
  }, []);

  // El cliente axios avisa cuando el servidor rechaza el token (401).
  useEffect(() => {
    const alExpirar = (e: Event) => {
      setUsuario(null);
      setCargando(false);
      const mensaje = (e as CustomEvent<string>).detail;
      navigate("/login", { replace: true, state: { mensaje } });
    };
    window.addEventListener("auth:expirada", alExpirar);
    return () => window.removeEventListener("auth:expirada", alExpirar);
  }, [navigate]);

  const login = useCallback(async (correo: string, contrasena: string) => {
    const r = await iniciarSesion(correo, contrasena);
    guardarToken(r.access_token);
    setUsuario(r.usuario);
    return r.usuario;
  }, []);

  const registrar = useCallback(
    (nombre: string, correo: string, contrasena: string) => registrarCuenta(nombre, correo, contrasena),
    []
  );

  const logout = useCallback(async () => {
    try {
      await cerrarSesionApi();
    } catch {
      /* el servidor no guarda la sesión: igual se cierra aquí */
    }
    borrarToken();
    setUsuario(null);
    navigate("/login", { replace: true, state: { mensaje: "Cerraste sesión correctamente." } });
  }, [navigate]);

  const valor = useMemo<AuthValor>(
    () => ({ usuario, cargando, login, registrar, logout, actualizarUsuario: setUsuario }),
    [usuario, cargando, login, registrar, logout]
  );

  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValor {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de AuthProvider");
  return ctx;
}
