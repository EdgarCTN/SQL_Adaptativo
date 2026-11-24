import axios from "axios";
import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

/**
 * Estado del servidor (arranque en frío del plan gratuito de Render).
 * Render duerme la API tras 15 min sin tráfico y tarda hasta ~1-2 min en despertar; Neon también
 * se suspende. Aquí se sondea /health con paciencia para que la pantalla lo muestre como algo
 * esperado («Despertando el servidor…») y no como un error de conexión del usuario.
 * Este módulo NO importa cliente.ts (evita ciclos) y no usa su interceptor (evita toasts de error).
 */

export const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api/v1";

export type EstadoServidor = "desconocido" | "despertando" | "listo" | "caido";

export const TIMEOUT_INTENTO_MS = 90_000; // cada sondeo puede esperar hasta 90 s
export const TIEMPO_MAXIMO_MS = 120_000; // tope total antes de declarar el servidor «caído»
export const ESPERAS_MS = [2_000, 3_000, 5_000]; // pausas entre sondeos; la última se repite
export const DORMIDO_TRAS_MS = 10 * 60_000; // Render duerme a los 15 min; se asume dormido a los 10
export const AVISO_TRAS_MS = 1_200; // no se anuncia «despertando» si /health responde enseguida

/** Pausa antes del sondeo número `intento + 1` (empieza en 0). */
export function esperaEntreIntentos(intento: number): number {
  return ESPERAS_MS[Math.min(Math.max(intento, 0), ESPERAS_MS.length - 1)];
}

/** 502/503/504: el proxy de Render responde así mientras el servicio duerme o arranca. */
export function esPuertaDeEnlace(status: number | null | undefined): boolean {
  return status === 502 || status === 503 || status === 504;
}

/** Interpreta una respuesta de /health: «listo» o «reintentar» (sigue despertando). */
export function evaluarHealth(status: number, datos: unknown): "listo" | "reintentar" {
  if (esPuertaDeEnlace(status)) return "reintentar";
  if (status === 200) {
    // 200 sin base_datos «ok» (o con una página HTML de espera): Neon puede estar reanudando.
    const bd = typeof datos === "object" && datos !== null ? (datos as { base_datos?: unknown }).base_datos : undefined;
    return bd === "ok" ? "listo" : "reintentar";
  }
  return "listo"; // cualquier otra respuesta HTTP prueba que el servidor está despierto
}

/** «Probablemente dormido»: nunca hubo una respuesta, o la última fue hace más de 10 min. */
export function estaProbablementeDormido(ultimoExito: number | null, ahora: number): boolean {
  return ultimoExito === null || ahora - ultimoExito > DORMIDO_TRAS_MS;
}

// ---- Estado (store mínimo para useSyncExternalStore) ----

interface Instantanea {
  estado: EstadoServidor;
  inicioEspera: number | null; // marca de tiempo en que empezó la espera actual
}

let instantanea: Instantanea = { estado: "desconocido", inicioEspera: null };
let ultimoExito: number | null = null;
let enCurso: Promise<boolean> | null = null;
const oyentes = new Set<() => void>();

function publicar(cambio: Partial<Instantanea>): void {
  instantanea = { ...instantanea, ...cambio };
  oyentes.forEach((o) => o());
}

function suscribir(oyente: () => void): () => void {
  oyentes.add(oyente);
  return () => {
    oyentes.delete(oyente);
  };
}

const leer = (): Instantanea => instantanea;

export const estadoServidor = (): EstadoServidor => instantanea.estado;
export const hayCalentamientoEnCurso = (): boolean => enCurso !== null;
export const probablementeDormido = (): boolean => estaProbablementeDormido(ultimoExito, Date.now());

/** Anota que el servidor respondió (cualquier petición normal con respuesta HTTP válida). */
export function registrarExito(): void {
  ultimoExito = Date.now();
  if (instantanea.estado === "caido") publicar({ estado: "listo" });
}

// ---- Calentamiento ----

// Instancia aparte, sin interceptores: ni token ni toasts. validateStatus permite leer cualquier status.
const sonda = axios.create({ baseURL: BASE_URL, validateStatus: () => true });

async function sondear(timeoutMs: number): Promise<"listo" | "reintentar"> {
  try {
    const r = await sonda.get("/health", { timeout: timeoutMs });
    return evaluarHealth(r.status, r.data);
  } catch {
    return "reintentar"; // error de red (sin CORS), timeout, etc.
  }
}

const dormir = (ms: number) => new Promise<void>((resolver) => window.setTimeout(resolver, ms));

async function sondearConReintentos(inicio: number): Promise<boolean> {
  for (let intento = 0; ; intento++) {
    const restante = TIEMPO_MAXIMO_MS - (Date.now() - inicio);
    if (restante < 1_000) return false;
    if ((await sondear(Math.min(TIMEOUT_INTENTO_MS, restante))) === "listo") return true;
    const restanteTrasSondeo = TIEMPO_MAXIMO_MS - (Date.now() - inicio);
    await dormir(Math.max(0, Math.min(esperaEntreIntentos(intento), restanteTrasSondeo)));
  }
}

/**
 * Comprueba (con paciencia) que la API responde. Devuelve true si quedó lista y false si se agotó el tiempo.
 * Si ya hay una comprobación en curso, devuelve la misma promesa (no duplica peticiones).
 */
export function calentarServidor(): Promise<boolean> {
  if (enCurso) return enCurso;
  const inicio = Date.now();
  // Si estaba «caído» y el usuario reintenta, se muestra «despertando» de inmediato.
  publicar({ inicioEspera: inicio, estado: instantanea.estado === "caido" ? "despertando" : instantanea.estado });

  const promesa = (async () => {
    // Solo se anuncia «despertando» si la respuesta tarda; así no parpadea con el servidor despierto.
    const aviso = window.setTimeout(() => {
      if (enCurso) publicar({ estado: "despertando" });
    }, AVISO_TRAS_MS);
    try {
      const listo = await sondearConReintentos(inicio);
      if (listo) ultimoExito = Date.now();
      publicar({ estado: listo ? "listo" : "caido", inicioEspera: null });
      return listo;
    } finally {
      window.clearTimeout(aviso);
      enCurso = null;
    }
  })();
  enCurso = promesa;
  return promesa;
}

// ---- Hooks para la interfaz ----

/** Solo el estado (no se vuelve a renderizar cada segundo). */
export function useEstadoServidor(): EstadoServidor {
  return useSyncExternalStore(suscribir, leer, leer).estado;
}

/** Estado, segundos de espera transcurridos y función para reintentar. */
export function useServidor(): { estado: EstadoServidor; segundos: number; reintentar: () => void } {
  const { estado, inicioEspera } = useSyncExternalStore(suscribir, leer, leer);
  const [ahora, setAhora] = useState(() => Date.now());

  useEffect(() => {
    if (inicioEspera === null) return;
    setAhora(Date.now());
    const temporizador = window.setInterval(() => setAhora(Date.now()), 1000);
    return () => window.clearInterval(temporizador);
  }, [inicioEspera]);

  const segundos = inicioEspera === null ? 0 : Math.max(0, Math.floor((ahora - inicioEspera) / 1000));
  const reintentar = useCallback(() => {
    void calentarServidor();
  }, []);
  return { estado, segundos, reintentar };
}
