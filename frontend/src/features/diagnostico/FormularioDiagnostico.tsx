import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ErrorApi, MSG_RED } from "../../api/cliente";
import { enviarRespuestas } from "../../api/lineaBase";
import type { Cuestionario, Parte } from "../../api/tiposLineaBase";
import type { Usuario } from "../../api/tipos";
import { useAuth } from "../../app/AuthContext";
import { DESTINO_TRAS_DIAGNOSTICO } from "../../app/destinos";
import BarraProgreso from "./BarraProgreso";
import { borrarBorrador, guardarBorrador, leerBorrador, RespuestaLocal, Respuestas } from "./borrador";
import EsquemaTablas from "./EsquemaTablas";
import PreguntaPrueba from "./PreguntaPrueba";
import PreguntaSeleccion from "./PreguntaSeleccion";
import {
  construirEnvio,
  contarPreguntas,
  contarRespondidas,
  esPrueba,
  pendientesDeParte,
} from "./validacion";

const MSG_FALLO_ENVIO =
  "No fue posible completar el diagnóstico en este momento. Tus respuestas siguen aquí: puedes reintentar el envío.";

interface Props {
  cuestionario: Cuestionario;
  usuario: Usuario;
  alRecargar: () => void;
}

export default function FormularioDiagnostico({ cuestionario, usuario, alRecargar }: Props) {
  const { actualizarUsuario } = useAuth();
  const navigate = useNavigate();
  const partes = cuestionario.partes;

  const [inicial] = useState(() => leerBorrador(usuario.id, cuestionario.id));
  const [paso, setPaso] = useState(Math.min(inicial?.paso ?? 0, partes.length)); // 0 = introducción
  const [respuestas, setRespuestas] = useState<Respuestas>(inicial?.respuestas ?? {});
  const [intentos, setIntentos] = useState<number[]>([]); // partes donde ya se intentó avanzar
  const [erroresServidor, setErroresServidor] = useState<Record<string, string>>({});
  const [enviando, setEnviando] = useState(false);
  const [errorEnvio, setErrorEnvio] = useState<string | null>(null);
  const [final, setFinal] = useState<string | null>(null);
  const tituloRef = useRef<HTMLHeadingElement>(null);

  // El borrador se conserva si se recarga la página y se borra al guardar.
  useEffect(() => {
    if (final === null) guardarBorrador(usuario.id, { cuestionarioId: cuestionario.id, paso, respuestas });
  }, [usuario.id, cuestionario.id, paso, respuestas, final]);

  useEffect(() => {
    window.scrollTo({ top: 0 });
    tituloRef.current?.focus();
  }, [paso]);

  const cambiar = (id: string, r: RespuestaLocal) => {
    setRespuestas((prev) => ({ ...prev, [id]: r }));
    setErroresServidor((prev) => {
      if (!prev[id]) return prev;
      const { [id]: _quitada, ...resto } = prev;
      return resto;
    });
  };

  const irAPrimeraPendiente = (ids: string[]) => {
    window.setTimeout(() => {
      const el = document.getElementById(`pregunta-${ids[0]}`);
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
      el?.focus({ preventScroll: true });
    }, 50);
  };

  const marcarIntento = (indices: number[]) => setIntentos((prev) => Array.from(new Set([...prev, ...indices])));

  const siguiente = () => {
    const pendientes = pendientesDeParte(partes[paso - 1], respuestas);
    if (pendientes.length) {
      marcarIntento([paso]);
      irAPrimeraPendiente(pendientes);
      return;
    }
    setPaso(paso + 1);
  };

  const manejarErrorEnvio = (e: unknown) => {
    if (e instanceof ErrorApi && e.status === 422 && Object.keys(e.detalles).length) {
      setErroresServidor(e.detalles);
      const idx = partes.findIndex((p) => p.preguntas.some((q) => e.detalles[q.id]));
      if (idx >= 0) setPaso(idx + 1);
      setErrorEnvio("Revisa las preguntas marcadas y vuelve a enviar.");
      return;
    }
    if (e instanceof ErrorApi && e.status === 409 && e.mensaje.startsWith("Ya completaste")) {
      borrarBorrador(usuario.id);
      actualizarUsuario({ ...usuario, linea_base_completada: true });
      setFinal(e.mensaje);
      return;
    }
    if (e instanceof ErrorApi && e.status === 403) {
      navigate("/consentimiento", { replace: true });
      return;
    }
    if (e instanceof ErrorApi && e.status === 409) {
      setErrorEnvio(e.mensaje);
      return;
    }
    setErrorEnvio(e instanceof ErrorApi && e.red ? `${MSG_RED} Tus respuestas siguen aquí.` : MSG_FALLO_ENVIO);
  };

  const enviar = async () => {
    setErrorEnvio(null);
    const faltan = partes
      .map((p, i) => ({ i, ids: pendientesDeParte(p, respuestas) }))
      .filter((x) => x.ids.length > 0);
    if (faltan.length) {
      marcarIntento(partes.map((_, i) => i + 1));
      setPaso(faltan[0].i + 1);
      irAPrimeraPendiente(faltan[0].ids);
      return;
    }
    setEnviando(true);
    try {
      const resultado = await enviarRespuestas(construirEnvio(cuestionario, respuestas));
      borrarBorrador(usuario.id);
      actualizarUsuario({ ...usuario, linea_base_completada: true });
      setFinal(resultado.mensaje);
    } catch (e) {
      manejarErrorEnvio(e);
    } finally {
      setEnviando(false);
    }
  };

  if (final !== null) {
    return (
      <section role="status" className="rounded-2xl border border-green-300 bg-green-50 p-6 text-center">
        <h1 ref={tituloRef} tabIndex={-1} className="text-2xl font-bold text-green-900">
          Diagnóstico completado
        </h1>
        <p className="mt-2 text-sm text-green-900">{final}</p>
        <button
          type="button"
          onClick={() => navigate(DESTINO_TRAS_DIAGNOSTICO, { replace: true })}
          className="mt-4 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
        >
          Continuar
        </button>
      </section>
    );
  }

  const total = contarPreguntas(partes);
  const respondidas = contarRespondidas(partes, respuestas);

  if (paso === 0) {
    return (
      <section className="rounded-2xl border border-slate-200 bg-white p-6">
        <h1 ref={tituloRef} tabIndex={-1} className="text-2xl font-bold text-slate-900">
          Diagnóstico inicial
        </h1>
        <p className="mt-3 text-sm text-slate-700">{cuestionario.introduccion}</p>
        <ul className="mt-3 list-inside list-disc text-sm text-slate-600">
          {partes.map((p) => (
            <li key={p.id}>{p.titulo}</li>
          ))}
        </ul>
        {respondidas > 0 && (
          <p role="status" className="mt-4 rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-900">
            Recuperamos tu avance: {respondidas} de {total} preguntas respondidas.
          </p>
        )}
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => setPaso(1)}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            {respondidas > 0 ? "Continuar" : "Comenzar"}
          </button>
          <Link to={DESTINO_TRAS_DIAGNOSTICO} className="text-sm font-medium text-indigo-700 underline">
            Hacerlo más tarde
          </Link>
        </div>
      </section>
    );
  }

  const parte: Parte = partes[paso - 1];
  const pendientes = pendientesDeParte(parte, respuestas);
  const mostrarPendientes = intentos.includes(paso);
  const esUltima = paso === partes.length;

  const errorDe = (id: string): string | undefined => {
    if (erroresServidor[id]) return erroresServidor[id];
    if (mostrarPendientes && pendientes.includes(id)) return "Falta responder esta pregunta.";
    return undefined;
  };

  return (
    <div className="space-y-4">
      <BarraProgreso
        valor={(respondidas / Math.max(total, 1)) * 100}
        etiqueta={`Parte ${paso} de ${partes.length} · ${respondidas} de ${total} preguntas respondidas`}
      />

      <h1 ref={tituloRef} tabIndex={-1} className="text-xl font-bold text-slate-900">
        {parte.titulo}
      </h1>

      {parte.instrucciones && parte.instrucciones.length > 0 && (
        <ul className="list-inside list-disc rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
          {parte.instrucciones.map((t) => (
            <li key={t}>{t}</li>
          ))}
        </ul>
      )}

      {parte.esquema && <EsquemaTablas tablas={parte.esquema.tablas} />}

      {mostrarPendientes && pendientes.length > 0 && (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          Te faltan {pendientes.length} {pendientes.length === 1 ? "pregunta" : "preguntas"} por responder:{" "}
          {pendientes.join(", ")}.
        </p>
      )}
      {errorEnvio && (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {errorEnvio}{" "}
          {errorEnvio.startsWith("El cuestionario cambió") && (
            <button type="button" onClick={alRecargar} className="font-semibold underline">
              Recargar cuestionario
            </button>
          )}
        </p>
      )}

      <div className="space-y-4">
        {parte.preguntas.map((p) =>
          esPrueba(p) ? (
            <PreguntaPrueba
              key={p.id}
              pregunta={p}
              respuesta={respuestas[p.id]}
              escala={parte.escala_confianza ?? {}}
              motivos={parte.omitir_motivos ?? []}
              error={errorDe(p.id)}
              alCambiar={(r) => cambiar(p.id, r)}
            />
          ) : (
            <PreguntaSeleccion
              key={p.id}
              pregunta={p}
              respuesta={respuestas[p.id]}
              error={errorDe(p.id)}
              alCambiar={(r) => cambiar(p.id, r)}
            />
          )
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3 pb-6">
        <button
          type="button"
          onClick={() => setPaso(paso - 1)}
          disabled={enviando}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
        >
          Atrás
        </button>
        {esUltima ? (
          <button
            type="button"
            onClick={() => void enviar()}
            disabled={enviando}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
          >
            {enviando ? "Enviando…" : errorEnvio ? "Reintentar envío" : "Enviar respuestas"}
          </button>
        ) : (
          <button
            type="button"
            onClick={siguiente}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            Siguiente
          </button>
        )}
        <Link to={DESTINO_TRAS_DIAGNOSTICO} className="text-sm font-medium text-indigo-700 underline">
          Hacerlo más tarde (se conserva tu avance)
        </Link>
      </div>
    </div>
  );
}
