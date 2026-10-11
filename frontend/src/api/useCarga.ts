import { useCallback, useEffect, useRef, useState } from "react";

import { mensajeDe } from "./cliente";

/** Carga datos al montar y cuando vuelve la conexión. `cargador` debe ser una función estable. */
export function useCarga<T>(cargador: () => Promise<T>) {
  const [datos, setDatos] = useState<T | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const version = useRef(0);

  const recargar = useCallback(async () => {
    const mia = ++version.current;
    setCargando(true);
    setError(null);
    try {
      const resultado = await cargador();
      if (mia === version.current) setDatos(resultado);
    } catch (e) {
      if (mia === version.current) setError(mensajeDe(e));
    } finally {
      if (mia === version.current) setCargando(false);
    }
  }, [cargador]);

  useEffect(() => {
    void recargar();
    return () => {
      version.current++;
    };
  }, [recargar]);

  useEffect(() => {
    const alReconectar = () => void recargar();
    window.addEventListener("api:reconectado", alReconectar);
    return () => window.removeEventListener("api:reconectado", alReconectar);
  }, [recargar]);

  return { datos, cargando, error, recargar };
}
