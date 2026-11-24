import axios, { AxiosError, InternalAxiosRequestConfig } from "axios";

import { mostrarToast } from "../components/Toasts";
import {
  BASE_URL,
  calentarServidor,
  esPuertaDeEnlace,
  hayCalentamientoEnCurso,
  probablementeDormido,
  registrarExito,
} from "./servidor";

const CLAVE_TOKEN = "token";

export const MSG_RED = "No pudimos conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.";
export const MSG_SERVIDOR_NO_DESPIERTA = "No logramos despertar el servidor. Puede ser un problema temporal. Inténtalo de nuevo en unos minutos.";
export const MSG_INESPERADO = "Ocurrió un problema inesperado. Inténtalo de nuevo en unos minutos.";
export const MSG_SESION_EXPIRADA = "Tu sesión expiró. Inicia sesión de nuevo.";

// Rutas donde un 401 significa «credenciales inválidas», no «sesión expirada».
const RUTAS_SIN_EXPIRACION = ["/auth/login", "/auth/registro", "/auth/logout"];
// Rutas cuyo fallo de red se ignora en silencio (sin aviso «No hay conexión»).
const RUTAS_SILENCIOSAS = ["/auth/logout", "/latido"];
// Rutas que nunca esperan a que el servidor despierte (la compuerta no las bloquea).
const RUTAS_SIN_COMPUERTA = [...RUTAS_SILENCIOSAS, "/health"];

type ConfigConMarca = InternalAxiosRequestConfig & { reintentoServidor?: boolean };

/** Sin red en el propio dispositivo: no tiene sentido esperar al servidor. */
const sinConexionLocal = () => typeof navigator !== "undefined" && navigator.onLine === false;

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

/**
 * Compuerta: si el servidor está probablemente dormido, la petición espera a que despierte y recién
 * entonces se envía (así no se reenvían POST ni se duplican registros). Los 15 s de timeout cuentan
 * desde que la petición sale, ya con el servidor despierto.
 */
cliente.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  const url = config.url ?? "";
  const exenta = RUTAS_SIN_COMPUERTA.some((r) => url.includes(r));
  if (!exenta && !sinConexionLocal() && (probablementeDormido() || hayCalentamientoEnCurso())) {
    const listo = await calentarServidor();
    if (!listo) throw new ErrorApi(MSG_SERVIDOR_NO_DESPIERTA, null, {}, true);
  }
  const token = leerToken();
  if (token) config.headers.set("Authorization", `Bearer ${token}`);
  return config;
});

/** Comprueba que el servidor responde; si sí, avisa a las pantallas para que recarguen. */
async function reintentarConexion(): Promise<void> {
  if (await calentarServidor()) {
    mostrarToast({ id: "red", tipo: "exito", mensaje: "Conexión restablecida." });
    window.dispatchEvent(new Event("api:reconectado"));
  } else {
    avisarSinConexion();
  }
}

function avisarSinConexion(): void {
  mostrarToast({
    id: "red",
    tipo: "error",
    mensaje: "No hay conexión con el servidor.",
    accion: { etiqueta: "Reintentar", alClick: () => void reintentarConexion() },
  });
}

/**
 * Fallo sin respuesta (o 502/503/504) en una petición hecha con el servidor supuestamente despierto.
 * Antes de culpar a la conexión, se comprueba si el servidor se durmió o está reanudando.
 */
async function manejarCaida(config: ConfigConMarca | undefined): Promise<unknown> {
  let avisar = true;
  if (!sinConexionLocal()) {
    const despierto = await calentarServidor();
    if (despierto) {
      const yaReintentada = config?.reintentoServidor === true;
      if (config && !yaReintentada && (config.method ?? "get").toLowerCase() === "get") {
        // Lectura (segura de repetir): se reintenta una vez ahora que el servidor responde.
        const reintento: ConfigConMarca = { ...config, reintentoServidor: true };
        return cliente.request(reintento);
      }
      // Escrituras no se reenvían solas. Sin aviso si el servidor ya responde; con aviso si la lectura falló dos veces.
      avisar = yaReintentada;
    }
  }
  if (avisar) avisarSinConexion();
  throw new ErrorApi(MSG_RED, null, {}, true);
}

cliente.interceptors.response.use(
  (r) => {
    registrarExito();
    return r;
  },
  async (error: unknown) => {
    if (axios.isCancel(error)) return Promise.reject(error);
    // Rechazo de la compuerta (el servidor no despertó): ya es un ErrorApi, se entrega tal cual.
    if (error instanceof ErrorApi) return Promise.reject(error);
    const fallo = error as AxiosError<{ mensaje?: string; detalles?: { campo: string; mensaje: string }[] }>;
    const url = fallo.config?.url ?? "";
    const silenciosa = RUTAS_SILENCIOSAS.some((r) => url.includes(r));
    const respuesta = fallo.response;
    const puertaDeEnlace = !!respuesta && esPuertaDeEnlace(respuesta.status);
    if (respuesta && !puertaDeEnlace) registrarExito(); // respondió: el servidor está despierto

    if (!respuesta || (puertaDeEnlace && !silenciosa)) {
      if (silenciosa) return Promise.reject(new ErrorApi(MSG_RED, null, {}, true));
      return manejarCaida(fallo.config);
    }

    const status = respuesta.status;

    if (status === 401 && !RUTAS_SIN_EXPIRACION.some((r) => url.includes(r))) {
      borrarToken();
      window.dispatchEvent(new CustomEvent("auth:expirada", { detail: MSG_SESION_EXPIRADA }));
      return Promise.reject(new ErrorApi(MSG_SESION_EXPIRADA, 401));
    }

    const datos = respuesta.data;
    const detalles: Record<string, string> = {};
    if (datos && Array.isArray(datos.detalles)) {
      for (const d of datos.detalles) if (d.campo && !detalles[d.campo]) detalles[d.campo] = d.mensaje;
    }
    const mensaje = status >= 500 ? MSG_INESPERADO : datos?.mensaje || MSG_INESPERADO;
    return Promise.reject(new ErrorApi(mensaje, status, detalles));
  }
);
