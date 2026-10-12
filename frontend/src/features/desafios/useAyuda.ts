import { useCallback, useEffect, useRef, useState } from "react";

import { pedirAyuda, valorarAyuda } from "../../api/ayuda";
import { ErrorApi } from "../../api/cliente";
import type { AyudaRecibida, RespuestaAyuda, TipoAyuda } from "../../api/tiposDesafios";
import { mostrarToast } from "../../components/Toasts";

export const MAX_MENSAJE_AYUDA = 500;
export const MSG_AYUDA_NO_DISPONIBLE =
  "No pudimos generar la ayuda en este momento. Puedes seguir con tu consulta y volver a pedirla en unos minutos.";
export const MSG_AYUDA_NO_UTILIZABLE = "No fue posible obtener una ayuda válida. Vuelve a solicitar ayuda.";
export const MSG_VALORACION = "No pudimos registrar tu valoración. Inténtalo de nuevo.";
const TIPOS: TipoAyuda[] = ["AY1", "AY2", "AY3", "AY4"];

const claveAyudas = (usuarioId: number, desafioId: number, sesionId: number) =>
  `desafio:ayudas:${usuarioId}:${desafioId}:${sesionId}`;

function leer(clave: string | null): AyudaRecibida[] {
  if (!clave) return [];
  try {
    const datos = JSON.parse(sessionStorage.getItem(clave) ?? "[]");
    return Array.isArray(datos) ? datos : [];
  } catch {
    return [];
  }
}

function escribir(clave: string | null, ayudas: AyudaRecibida[]): void {
  if (!clave) return;
  try {
    sessionStorage.setItem(clave, JSON.stringify(ayudas));
  } catch {
    /* sin almacenamiento: las ayudas solo viven en pantalla */
  }
}

/** Una respuesta sirve si trae solicitud, tipo conocido y mensaje con texto (EX2: si no, se invita a pedirla de nuevo). */
export function ayudaUtilizable(r: Partial<RespuestaAyuda> | null | undefined): r is RespuestaAyuda {
  return (
    !!r &&
    typeof r.solicitud_id === "number" &&
    !!r.tipo_ayuda &&
    TIPOS.includes(r.tipo_ayuda) &&
    typeof r.mensaje === "string" &&
    r.mensaje.trim().length > 0
  );
}

interface Opciones {
  desafioId: number;
  sesionId: number | null;
  usuarioId: number;
  alNoDisponible: (mensaje: string) => void;
  alRecargar: () => void;
}

export function useAyuda({ desafioId, sesionId, usuarioId, alNoDisponible, alRecargar }: Opciones) {
  const clave = sesionId ? claveAyudas(usuarioId, desafioId, sesionId) : null;
  const [ayudas, setAyudas] = useState<AyudaRecibida[]>(() => leer(clave));
  const actuales = useRef(ayudas);
  const [pidiendo, setPidiendo] = useState(false);
  const [errorAyuda, setErrorAyuda] = useState<string | null>(null);
  const [avisoSolo, setAvisoSolo] = useState<string | null>(null);
  const [valorando, setValorando] = useState<number | null>(null);

  const fijar = useCallback(
    (lista: AyudaRecibida[]) => {
      actuales.current = lista;
      setAyudas(lista);
      escribir(clave, lista);
    },
    [clave],
  );

  // Cambió la sesión (nueva, abandonada o recargada): se vuelven a leer sus ayudas.
  useEffect(() => {
    const lista = leer(clave);
    actuales.current = lista;
    setAyudas(lista);
    setErrorAyuda(null);
    setAvisoSolo(null);
  }, [clave]);

  /** Devuelve true si se mostró una respuesta (para limpiar el mensaje opcional). */
  const pedir = async (mensaje: string): Promise<boolean> => {
    if (pidiendo || !clave) return false;
    setPidiendo(true);
    setErrorAyuda(null);
    setAvisoSolo(null);
    try {
      const r = await pedirAyuda(desafioId, mensaje.trim().slice(0, MAX_MENSAJE_AYUDA) || undefined);
      if (r && r.tipo_ayuda === null && r.desafio_marcado_nr && r.aviso) {
        setAvisoSolo(r.aviso); // ya vio la solución: solo se le recuerda
        return true;
      }
      if (!ayudaUtilizable(r)) {
        setErrorAyuda(MSG_AYUDA_NO_UTILIZABLE);
        return false;
      }
      fijar([
        ...actuales.current,
        {
          solicitud_id: r.solicitud_id as number,
          tipo_ayuda: r.tipo_ayuda as TipoAyuda,
          mensaje: (r.mensaje as string).trim(),
          codigo_sql: r.codigo_sql ?? null,
          etiquetas: Array.isArray(r.etiquetas) ? r.etiquetas : [],
          reformulada: !!r.reformulada,
          sugerencia: r.sugerencia ?? null,
          aviso: r.aviso ?? null,
          valoracion: null,
        },
      ]);
      return true;
    } catch (e) {
      if (e instanceof ErrorApi && e.status === 404) alNoDisponible(e.mensaje);
      else if (e instanceof ErrorApi && e.status === 409) {
        mostrarToast({ tipo: "info", mensaje: e.mensaje });
        alRecargar();
      } else setErrorAyuda(MSG_AYUDA_NO_DISPONIBLE); // nunca un error técnico
      return false;
    } finally {
      setPidiendo(false);
    }
  };

  const valorar = async (solicitudId: number, valor: 1 | -1) => {
    if (valorando !== null) return;
    setValorando(solicitudId);
    try {
      await valorarAyuda(solicitudId, valor);
      fijar(actuales.current.map((a) => (a.solicitud_id === solicitudId ? { ...a, valoracion: valor } : a)));
    } catch {
      mostrarToast({ tipo: "error", mensaje: MSG_VALORACION });
    } finally {
      setValorando(null);
    }
  };

  const descartar = () => {
    if (clave) {
      try {
        sessionStorage.removeItem(clave);
      } catch {
        /* nada que borrar */
      }
    }
  };

  return { ayudas, pidiendo, errorAyuda, avisoSolo, valorando, pedir, valorar, descartar };
}
