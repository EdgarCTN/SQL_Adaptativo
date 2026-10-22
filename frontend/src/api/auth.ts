import { cliente } from "./cliente";
import type { Mensaje, TokenOut, Usuario } from "./tipos";

export interface EdicionPerfil {
  nombre?: string;
  contrasena_actual?: string;
  contrasena_nueva?: string;
}

export const registrarCuenta = (nombre: string, correo: string, contrasena: string) =>
  cliente.post<Usuario>("/auth/registro", { nombre, correo, contrasena }).then((r) => r.data);

export const iniciarSesion = (correo: string, contrasena: string) =>
  cliente.post<TokenOut>("/auth/login", { correo, contrasena }).then((r) => r.data);

export const cerrarSesionApi = () =>
  cliente.post<Mensaje>("/auth/logout", undefined, { timeout: 5000 }).then((r) => r.data);

export const obtenerYo = () => cliente.get<Usuario>("/auth/yo").then((r) => r.data);

export const verPerfil = () => cliente.get<Usuario>("/perfil").then((r) => r.data);

export const editarPerfil = (datos: EdicionPerfil) =>
  cliente.put<Usuario>("/perfil", datos).then((r) => r.data);
