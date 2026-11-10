import { useCallback, useEffect, useRef, useState } from "react";

import { obtenerAyudas, pedirAyuda, valorarAyuda } from "../../api/ayuda";
import { ErrorApi } from "../../api/cliente";
import type { AyudaRecibida, RespuestaAyuda, TipoAyuda } from "../../api/tiposDesafios";
import { mostrarToast } from "../../components/Toasts";

export const MAX_MENSAJE_AYUDA = 500;
export const MSG_AYUDA_NO_DISPONIBLE =
  "No pudimos generar la ayuda en este momento. Puedes seguir con tu consulta y volver a pedirla en unos minutos.";
export const MSG_AYUDA_NO_UTILIZABLE = "No fue posible obtener una ayuda válida. Vuelve a solicitar ayuda.";
export const MSG_VALORACION = "No pudimos registrar tu valoración. Inténtalo de nuevo.";
const TIPOS: TipoAyuda[] = ["AY1", "AY2", "AY3", "AY4"];

export function ayudaUtilizable(r: Partial<RespuestaAyuda> | null | undefined): r is RespuestaAyuda {
  return !!r && typeof r.solicitud_id === "number" && !!r.tipo_ayuda && TIPOS.includes(r.tipo_ayuda)
    && typeof r.mensaje === "string" && r.mensaje.trim().length > 0;
}

function recibida(r: RespuestaAyuda, sola = false): AyudaRecibida {
  return {
    solicitud_id: r.solicitud_id as number, tipo_ayuda: r.tipo_ayuda as TipoAyuda,
    mensaje: (r.mensaje as string).trim(), codigo_sql: r.codigo_sql ?? null,
    etiquetas: Array.isArray(r.etiquetas) ? r.etiquetas : [], reformulada: !!r.reformulada,
    sugerencia: r.sugerencia ?? null, aviso: r.aviso ?? null, valoracion: null,
    mostrada_sola: r.mostrada_sola ?? sola,
  };
}

interface Opciones {
  desafioId: number;
  sesionId: number | null;
  usuarioId: number;
  alNoDisponible: (mensaje: string) => void;
  alRecargar: () => void;
}

export function useAyuda({ desafioId, sesionId, usuarioId, alNoDisponible, alRecargar }: Opciones) {
  const clave = `${usuarioId}:${desafioId}:${sesionId ?? "ultima"}`;
  const vigente = useRef(clave);
  vigente.current = clave;
  const callbacks = useRef({ alNoDisponible, alRecargar });
  callbacks.current = { alNoDisponible, alRecargar };
  const [ayudas, setAyudas] = useState<AyudaRecibida[]>([]);
  const actuales = useRef<AyudaRecibida[]>([]);
  const [pidiendo, setPidiendo] = useState(false);
  const peticion = useRef(false);
  const [cargandoAyudas, setCargandoAyudas] = useState(true);
  const [errorHistorial, setErrorHistorial] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [errorAyuda, setErrorAyuda] = useState<string | null>(null);
  const [avisoSolo, setAvisoSolo] = useState<string | null>(null);
  const [valorando, setValorando] = useState<number | null>(null);

  const fijar = useCallback((lista: AyudaRecibida[]) => {
    actuales.current = lista;
    setAyudas(lista);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fijar([]);
    peticion.current = false;
    setPidiendo(false);
    setValorando(null);
    setErrorAyuda(null);
    setAvisoSolo(null);
    setErrorHistorial(null);
    setCargandoAyudas(true);
    obtenerAyudas(desafioId, sesionId, controller.signal).then((r) => {
      if (controller.signal.aborted || vigente.current !== clave) return;
      // Una oferta automática puede llegar mientras se recupera el historial: no se pierde ni se duplica.
      const lista = new Map(r.ayudas.map((a) => [a.solicitud_id, a]));
      for (const a of actuales.current) lista.set(a.solicitud_id, a);
      fijar([...lista.values()].sort((a, b) => a.solicitud_id - b.solicitud_id));
    }).catch(() => {
      if (!controller.signal.aborted && vigente.current === clave)
        setErrorHistorial("No pudimos recuperar tus ayudas guardadas. Vuelve a intentarlo.");
    }).finally(() => {
      if (!controller.signal.aborted && vigente.current === clave) setCargandoAyudas(false);
    });
    return () => controller.abort();
  }, [clave, desafioId, sesionId, revision, fijar]);

  const recargarAyudas = () => setRevision((n) => n + 1);

  const pedir = async (mensaje: string): Promise<boolean> => {
    if (peticion.current || !sesionId || cargandoAyudas || errorHistorial) return false;
    peticion.current = true;
    setPidiendo(true);
    setErrorAyuda(null);
    setAvisoSolo(null);
    try {
      const r = await pedirAyuda(desafioId, mensaje.trim().slice(0, MAX_MENSAJE_AYUDA) || undefined);
      if (vigente.current !== clave) return false;
      if (r && r.tipo_ayuda === null && r.desafio_marcado_nr && r.aviso) {
        setAvisoSolo(r.aviso);
        return true;
      }
      if (!ayudaUtilizable(r)) {
        setErrorAyuda(MSG_AYUDA_NO_UTILIZABLE);
        return false;
      }
      fijar([...actuales.current.filter((a) => a.solicitud_id !== r.solicitud_id), recibida(r)]);
      return true;
    } catch (e) {
      if (vigente.current !== clave) return false;
      if (e instanceof ErrorApi && e.status === 404) callbacks.current.alNoDisponible(e.mensaje);
      else if (e instanceof ErrorApi && e.status === 409) {
        mostrarToast({ tipo: "info", mensaje: e.mensaje });
        callbacks.current.alRecargar();
      } else setErrorAyuda(MSG_AYUDA_NO_DISPONIBLE);
      return false;
    } finally {
      if (vigente.current === clave) {
        peticion.current = false;
        setPidiendo(false);
      }
    }
  };

  const incorporar = (r: RespuestaAyuda, sola = true): boolean => {
    if (!sesionId || !ayudaUtilizable(r)) return false;
    if (actuales.current.some((a) => a.solicitud_id === r.solicitud_id)) return true;
    fijar([...actuales.current, recibida(r, sola)]);
    return true;
  };

  const valorar = async (solicitudId: number, valor: 1 | -1) => {
    if (valorando !== null) return;
    setValorando(solicitudId);
    try {
      await valorarAyuda(solicitudId, valor);
      if (vigente.current === clave)
        fijar(actuales.current.map((a) => a.solicitud_id === solicitudId ? { ...a, valoracion: valor } : a));
    } catch {
      if (vigente.current === clave) mostrarToast({ tipo: "error", mensaje: MSG_VALORACION });
    } finally {
      if (vigente.current === clave) setValorando(null);
    }
  };

  const descartar = () => fijar([]); // El historial permanece en el servidor.
  return { ayudas, pidiendo, errorAyuda, avisoSolo, valorando, pedir, incorporar, valorar, descartar,
    cargandoAyudas, errorHistorial, recargarAyudas };
}
