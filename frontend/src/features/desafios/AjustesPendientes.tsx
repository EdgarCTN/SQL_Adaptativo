import { useCallback, useEffect, useRef, useState } from "react";

import { listarAjustesPendientes, responderAjuste } from "../../api/ajustes";
import type { AjustePendiente } from "../../api/ajustes";
import { mensajeDe } from "../../api/cliente";
import { mostrarToast } from "../../components/Toasts";
import DialogoRetiro from "./DialogoRetiro";

interface Props {
  /** Cambia (p. ej. un contador) para volver a consultar tras cerrar un desafío. */
  refrescar?: number;
  /** Abre el diálogo solo, una vez por aviso (tras un cierre de desafío). */
  abrirPregunta?: boolean;
}

/** R13 (pregunta 3.4): retiros que esperan al estudiante. «aviso_previo» → botón «Mantener la ayuda»; «preguntar» → diálogo. */
export default function AjustesPendientes({ refrescar = 0, abrirPregunta = false }: Props) {
  const [lista, setLista] = useState<AjustePendiente[]>([]);
  const [enDialogo, setEnDialogo] = useState<AjustePendiente | null>(null);
  const [ocupado, setOcupado] = useState<number | null>(null);
  const yaAbiertos = useRef(new Set<number>());

  const cargar = useCallback(async () => {
    try {
      const ajustes = await listarAjustesPendientes();
      setLista(ajustes);
      if (abrirPregunta) {
        const nueva = ajustes.find((a) => a.modo === "preguntar" && !yaAbiertos.current.has(a.id));
        if (nueva) {
          yaAbiertos.current.add(nueva.id);
          setEnDialogo(nueva);
        }
      }
    } catch {
      /* es un aviso opcional: si falla, la pantalla sigue funcionando sin él */
    }
  }, [abrirPregunta]);

  useEffect(() => {
    void cargar();
  }, [cargar, refrescar]);

  const responder = async (a: AjustePendiente, accion: "aceptar" | "mantener") => {
    if (ocupado !== null) return;
    setOcupado(a.id);
    try {
      const r = await responderAjuste(a.id, accion);
      mostrarToast({ tipo: "info", mensaje: r.mensaje, duracion: 8000 });
      setLista((prev) => prev.filter((x) => x.id !== a.id));
      setEnDialogo(null);
    } catch (e) {
      mostrarToast({ tipo: "error", mensaje: mensajeDe(e) });
      void cargar();
      setEnDialogo(null);
    } finally {
      setOcupado(null);
    }
  };

  if (lista.length === 0 && !enDialogo) return null;
  return (
    <div className="space-y-2" aria-live="polite">
      {lista.map((a) => (
        <div key={a.id} role="status" className="rounded-lg border border-indigo-300 bg-indigo-50 p-3 text-sm text-indigo-900">
          <p>{a.texto}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {a.modo === "aviso_previo" ? (
              <button
                type="button"
                disabled={ocupado !== null}
                onClick={() => void responder(a, "mantener")}
                className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
              >
                Mantener la ayuda
              </button>
            ) : (
              <button
                type="button"
                disabled={ocupado !== null}
                onClick={() => setEnDialogo(a)}
                className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
              >
                Responder
              </button>
            )}
          </div>
        </div>
      ))}
      {enDialogo && (
        <DialogoRetiro
          texto={enDialogo.texto}
          ocupado={ocupado === enDialogo.id}
          onAceptar={() => void responder(enDialogo, "aceptar")}
          onMantener={() => void responder(enDialogo, "mantener")}
          onCerrar={() => setEnDialogo(null)}
        />
      )}
    </div>
  );
}
