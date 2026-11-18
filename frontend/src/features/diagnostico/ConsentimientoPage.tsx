import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { obtenerEstado, registrarConsentimiento } from "../../api/lineaBase";
import { ErrorApi, MSG_INESPERADO } from "../../api/cliente";
import { useCarga } from "../../api/useCarga";
import { DESTINO_TRAS_DIAGNOSTICO } from "../../app/destinos";
import EstadoContenedor from "../../components/EstadoContenedor";
import MarcoDiagnostico from "./MarcoDiagnostico";

export default function ConsentimientoPage() {
  const navigate = useNavigate();
  const { datos, cargando, error, recargar } = useCarga(obtenerEstado);
  const [enviando, setEnviando] = useState(false);
  const [errorEnvio, setErrorEnvio] = useState<string | null>(null);
  const [rechazado, setRechazado] = useState(false);

  const aceptar = async () => {
    setErrorEnvio(null);
    setEnviando(true);
    try {
      await registrarConsentimiento(true);
      navigate("/diagnostico", { replace: true });
    } catch (e) {
      setErrorEnvio(e instanceof ErrorApi ? e.mensaje : MSG_INESPERADO);
    } finally {
      setEnviando(false);
    }
  };

  // Ya aceptó antes: continúa con el cuestionario.
  if (datos?.consentimiento_aceptado && !datos.linea_base_completada) {
    return <Navigate to="/diagnostico" replace />;
  }

  return (
    <MarcoDiagnostico>
      <EstadoContenedor cargando={cargando && !datos} error={error} onReintentar={() => void recargar()}>
        {datos?.linea_base_completada ? (
          <section className="rounded-2xl border border-slate-200 bg-white p-6 text-center">
            <h1 className="text-xl font-bold text-slate-900">Ya completaste tu diagnóstico inicial</h1>
            <Link
              to={DESTINO_TRAS_DIAGNOSTICO}
              className="mt-4 inline-block rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
            >
              Continuar
            </Link>
          </section>
        ) : rechazado ? (
          <section role="alert" className="rounded-2xl border border-amber-300 bg-amber-50 p-6">
            <h1 className="text-xl font-bold text-amber-900">Necesitamos tu consentimiento</h1>
            <p className="mt-2 text-sm text-amber-900">
              El consentimiento es necesario para completar el diagnóstico inicial. No guardamos ninguna respuesta ni
              dato del diagnóstico.
            </p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                onClick={() => setRechazado(false)}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
              >
                Volver a leer la información
              </button>
              <Link
                to={DESTINO_TRAS_DIAGNOSTICO}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Usar la plataforma sin diagnóstico
              </Link>
            </div>
          </section>
        ) : (
          <section className="rounded-2xl border border-slate-200 bg-white p-6">
            <h1 className="text-2xl font-bold text-slate-900">Consentimiento informado</h1>
            <p className="mt-1 text-sm text-slate-600">
              Antes del diagnóstico inicial, te explicamos cómo usaremos tus datos.
            </p>

            {/* PROVISIONAL (RNF-22): texto versión 1.1 pendiente de validación por la profesora o el comité de ética.
                Si cambia, sube VERSION_CONSENTIMIENTO en backend/app/modules/linea_base/service.py. Ver docs/PROVISIONALES.md. */}
            <div className="mt-4 space-y-4 text-sm text-slate-700">
              <div>
                <h2 className="font-semibold text-slate-900">¿Qué es esta plataforma?</h2>
                <p>
                  Desafíos SQL te propone ejercicios de SQL y ajusta la dificultad y la ayuda que recibes según tu
                  nivel. Forma parte de una investigación (tesis) sobre el apoyo adaptativo en el aprendizaje de SQL.
                </p>
              </div>
              <div>
                <h2 className="font-semibold text-slate-900">¿Qué datos guardamos?</h2>
                <ul className="list-disc space-y-1 pl-5">
                  <li>Tu nombre y tu correo, para tu cuenta.</li>
                  <li>Tus respuestas del diagnóstico inicial y tus preferencias de ayuda.</li>
                  <li>
                    En los desafíos: cada consulta SQL que envías y lo que devuelve, si resuelves, abandonas u omites,
                    y cuánto tiempo trabajas (medimos tu actividad en la página).
                  </li>
                  <li>Las ayudas que pides o recibes, si te sirvieron, y los cambios de tu nivel de ayuda.</li>
                </ul>
              </div>
              <div>
                <h2 className="font-semibold text-slate-900">¿Qué se envía a la inteligencia artificial?</h2>
                <p>
                  Cuando pides ayuda, o cuando la plataforma te la muestra, se envía a un proveedor externo de
                  inteligencia artificial el enunciado del desafío, tu consulta, el resultado que obtuviste, tus
                  errores recientes y el mensaje que escribas. No se envía tu nombre ni tu correo. Si la plataforma
                  está en modo de demostración, no se envía nada.
                </p>
              </div>
              <div>
                <h2 className="font-semibold text-slate-900">¿Para qué los usaremos y quién los ve?</h2>
                <p>
                  Para definir tu punto de partida, adaptar los desafíos y la ayuda, y analizar con fines académicos
                  si este enfoque funciona. En el análisis tu identidad se reemplaza por un código (seudónimo): los
                  informes del docente muestran grupos, no personas, y no incluyen tu nombre, tu correo ni el texto
                  de tus consultas. Solo el administrador de la plataforma ve tu nombre y tu correo, en la gestión de
                  cuentas. Los resultados de la investigación se presentarán de forma agregada y sin identificarte.
                </p>
              </div>
              <div>
                <h2 className="font-semibold text-slate-900">Tu decisión</h2>
                <p>
                  Tu participación es voluntaria. Si no aceptas, no guardaremos ninguna respuesta del diagnóstico y no
                  podrás completarlo.
                </p>
              </div>
            </div>

            {datos && <p className="mt-4 text-xs text-slate-500">Versión del texto: {datos.version_consentimiento}</p>}

            {errorEnvio && (
              <p role="alert" className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
                {errorEnvio}
              </p>
            )}

            <div className="mt-5 flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => void aceptar()}
                disabled={enviando}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
              >
                {enviando ? "Guardando…" : errorEnvio ? "Reintentar" : "Acepto y continuar"}
              </button>
              <button
                type="button"
                onClick={() => setRechazado(true)}
                disabled={enviando}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
              >
                No acepto
              </button>
              <Link to={DESTINO_TRAS_DIAGNOSTICO} className="text-sm font-medium text-indigo-700 underline">
                Hacerlo más tarde
              </Link>
            </div>
          </section>
        )}
      </EstadoContenedor>
    </MarcoDiagnostico>
  );
}
