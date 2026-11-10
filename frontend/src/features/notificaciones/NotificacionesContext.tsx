import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";

import { responderAjuste } from "../../api/ajustes";
import { mensajeDe } from "../../api/cliente";
import {
  EVENTO_NOTIFICACIONES_ACTUALIZADAS,
  listarNotificaciones,
  marcarNotificacionLeida,
  marcarTodasNotificacionesLeidas,
} from "../../api/notificaciones";
import type { Notificacion } from "../../api/notificaciones";
import { mostrarToast } from "../../components/Toasts";

interface ValorNotificaciones {
  notificaciones: Notificacion[];
  noLeidas: number;
  cargando: boolean;
  error: string | null;
  ocupadoId: number | null;
  recargar: () => void;
  marcarLeida: (id: number) => Promise<void>;
  marcarTodas: () => Promise<void>;
  responder: (notificacion: Notificacion, accion: "aceptar" | "mantener") => Promise<void>;
}

const ContextoNotificaciones = createContext<ValorNotificaciones | null>(null);

export function NotificacionesProvider({ children, activo = true }: { children: ReactNode; activo?: boolean }) {
  const [notificaciones, setNotificaciones] = useState<Notificacion[]>([]);
  const [noLeidas, setNoLeidas] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ocupadoId, setOcupadoId] = useState<number | null>(null);
  const enCurso = useRef(false);
  const lecturasEnCurso = useRef(new Set<number>());
  const [revision, setRevision] = useState(0);

  const cargar = useCallback(async () => {
    if (!activo) return;
    if (enCurso.current) return;
    enCurso.current = true;
    try {
      const datos = await listarNotificaciones();
      setNotificaciones(datos.notificaciones);
      setNoLeidas(datos.no_leidas);
      setError(null);
    } catch (e) {
      setError(mensajeDe(e));
    } finally {
      setCargando(false);
      enCurso.current = false;
    }
  }, [activo]);

  const recargar = useCallback(() => {
    setError(null);
    setCargando(true);
    setRevision((r) => r + 1);
  }, []);

  useEffect(() => {
    if (!activo) {
      setCargando(false);
      return;
    }
    setCargando(true);
    void cargar();
  }, [activo, cargar, revision]);

  useEffect(() => {
    if (!activo) return;
    const refrescarSiVisible = () => {
      if (document.visibilityState === "visible") void cargar();
    };
    const timer = window.setInterval(refrescarSiVisible, 60_000);
    document.addEventListener("visibilitychange", refrescarSiVisible);
    window.addEventListener(EVENTO_NOTIFICACIONES_ACTUALIZADAS, refrescarSiVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", refrescarSiVisible);
      window.removeEventListener(EVENTO_NOTIFICACIONES_ACTUALIZADAS, refrescarSiVisible);
    };
  }, [activo, cargar]);

  const marcarLeida = useCallback(async (id: number) => {
    if (lecturasEnCurso.current.has(id)) return;
    lecturasEnCurso.current.add(id);
    const noLeida = notificaciones.some((n) => n.id === id && !n.leida);
    try {
      await marcarNotificacionLeida(id);
      setNotificaciones((lista) => lista.map((n) => n.id === id ? { ...n, leida: true } : n));
      if (noLeida) setNoLeidas((actual) => Math.max(0, actual - 1));
    } catch (e) {
      mostrarToast({ tipo: "error", mensaje: mensajeDe(e) });
    } finally {
      lecturasEnCurso.current.delete(id);
    }
  }, [notificaciones]);

  const marcarTodas = useCallback(async () => {
    try {
      await marcarTodasNotificacionesLeidas();
      setNotificaciones((lista) => lista.map((n) => ({ ...n, leida: true })));
      setNoLeidas(0);
    } catch (e) {
      mostrarToast({ tipo: "error", mensaje: mensajeDe(e) });
    }
  }, []);

  const responder = useCallback(async (notificacion: Notificacion, accion: "aceptar" | "mantener") => {
    if (notificacion.ajuste_id === null || ocupadoId !== null) return;
    setOcupadoId(notificacion.id);
    try {
      const resultado = await responderAjuste(notificacion.ajuste_id, accion);
      mostrarToast({ tipo: "exito", mensaje: resultado.mensaje });
      await cargar();
    } catch (e) {
      mostrarToast({ tipo: "error", mensaje: mensajeDe(e) });
    } finally {
      setOcupadoId(null);
    }
  }, [cargar, ocupadoId]);

  const valor = useMemo(() => ({
    notificaciones, noLeidas, cargando, error, ocupadoId, recargar, marcarLeida, marcarTodas, responder,
  }), [notificaciones, noLeidas, cargando, error, ocupadoId, recargar, marcarLeida, marcarTodas, responder]);

  return <ContextoNotificaciones.Provider value={valor}>{children}</ContextoNotificaciones.Provider>;
}

export function useNotificaciones(): ValorNotificaciones {
  const contexto = useContext(ContextoNotificaciones);
  if (!contexto) throw new Error("useNotificaciones debe usarse dentro de NotificacionesProvider");
  return contexto;
}
