import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

import { mostrarToast } from "../components/Toasts";

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";
const CLAVE_TOKEN = "token";

export const MSG_RED = "No pudimos conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.";
export const MSG_INESPERADO = "Ocurrió un problema inesperado. Inténtalo de nuevo en unos minutos.";
export const MSG_SESION_EXPIRADA = "Tu sesión expiró. Inicia sesión de nuevo.";

// Rutas donde un 401 significa «credenciales inválidas», no «sesión expirada».
const RUTAS_SIN_EXPIRACION = ["/auth/login", "/auth/registro"];

export class ErrorApi extends Error {
  status: number | null;
  detalles: Record<string, string>;
  red: boolean;

  constructor(mensaje: string, status: number | null, detalles: Record<string, string> = {}, red = false) {
    super(mensaje);
    this.name = "ErrorApi";
    this.status = status;
    this.detalles = detalles;
    this.red = red;
  }

  get mensaje(): string {
    return this.message;
  }
}

export function mensajeDe(e: unknown): string {
  return e instanceof ErrorApi ? e.mensaje : MSG_INESPERADO;
}

export function leerToken(): string | null {
  try {
    return localStorage.getItem(CLAVE_TOKEN);
  } catch {
    return null;
  }
}

export function guardarToken(token: string): void {
  try {
    localStorage.setItem(CLAVE_TOKEN, token);
  } catch {
    /* sin almacenamiento: la sesión dura mientras la pestaña siga abierta */
  }
}

export function borrarToken(): void {
  try {
    localStorage.removeItem(CLAVE_TOKEN);
  } catch {
    /* nada que borrar */
  }
}

export const cliente = axios.create({ baseURL: BASE_URL, timeout: 15000 });

cliente.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = leerToken();
  if (token) config.headers.set("Authorization", `Bearer ${token}`);
  return config;
});

/** Comprueba que el servidor responde; si sí, avisa a las pantallas para que recarguen. */
async function reintentarConexion(): Promise<void> {
  try {
    await cliente.get("/health");
    mostrarToast({ id: "red", tipo: "exito", mensaje: "Conexión restablecida." });
    window.dispatchEvent(new Event("api:reconectado"));
  } catch {
    /* el interceptor ya muestra de nuevo el aviso con «Reintentar» */
  }
}

cliente.interceptors.response.use(
  (r) => r,
  (error: AxiosError<{ mensaje?: string; detalles?: { campo: string; mensaje: string }[] }>) => {
    if (!error.response) {
      mostrarToast({
        id: "red",
        tipo: "error",
        mensaje: "No hay conexión con el servidor.",
        accion: { etiqueta: "Reintentar", alClick: () => void reintentarConexion() },
      });
      return Promise.reject(new ErrorApi(MSG_RED, null, {}, true));
    }

    const status = error.response.status;
    const url = error.config?.url ?? "";

    if (status === 401 && !RUTAS_SIN_EXPIRACION.some((r) => url.includes(r))) {
      borrarToken();
      window.dispatchEvent(new CustomEvent("auth:expirada", { detail: MSG_SESION_EXPIRADA }));
      return Promise.reject(new ErrorApi(MSG_SESION_EXPIRADA, 401));
    }

    const datos = error.response.data;
    const detalles: Record<string, string> = {};
    if (datos && Array.isArray(datos.detalles)) {
      for (const d of datos.detalles) if (d.campo && !detalles[d.campo]) detalles[d.campo] = d.mensaje;
    }
    const mensaje = status >= 500 ? MSG_INESPERADO : datos?.mensaje || MSG_INESPERADO;
    return Promise.reject(new ErrorApi(mensaje, status, detalles));
  }
);
