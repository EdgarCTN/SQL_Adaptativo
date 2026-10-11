import { Link, Navigate } from "react-router-dom";

import { obtenerCuestionario, obtenerEstado } from "../../api/lineaBase";
import type { Cuestionario, EstadoLineaBase } from "../../api/tiposLineaBase";
import { useCarga } from "../../api/useCarga";
import { useAuth } from "../../app/AuthContext";
import { DESTINO_TRAS_DIAGNOSTICO } from "../../app/destinos";
import EstadoContenedor from "../../components/EstadoContenedor";
import FormularioDiagnostico from "./FormularioDiagnostico";
import MarcoDiagnostico from "./MarcoDiagnostico";

const MSG_NO_DISPONIBLE = "El cuestionario no puede presentarse en este momento. Inténtalo de nuevo más tarde.";

interface Datos {
  estado: EstadoLineaBase;
  cuestionario: Cuestionario | null;
}

async function cargarDiagnostico(): Promise<Datos> {
  const estado = await obtenerEstado();
  if (estado.siguiente_paso !== "cuestionario") return { estado, cuestionario: null };
  return { estado, cuestionario: await obtenerCuestionario() };
}

export default function DiagnosticoPage() {
  const { usuario } = useAuth();
  const { datos, cargando, error, recargar } = useCarga(cargarDiagnostico);

  if (datos && !datos.estado.linea_base_completada && !datos.estado.consentimiento_aceptado) {
    return <Navigate to="/consentimiento" replace />;
  }

  const completado = datos?.estado.linea_base_completada === true;
  // EX2: sin cuestionario disponible se informa y se permite reintentar.
  const errorMostrado = error ?? (datos && !completado && !datos.cuestionario ? MSG_NO_DISPONIBLE : null);

  return (
    <MarcoDiagnostico>
      <EstadoContenedor
        cargando={cargando && !datos}
        error={errorMostrado}
        vacio={!!datos?.cuestionario && datos.cuestionario.partes.length === 0}
        mensajeVacio="El cuestionario todavía no tiene preguntas."
        onReintentar={() => void recargar()}
      >
        {completado ? (
          <section className="rounded-2xl border border-slate-200 bg-white p-6 text-center">
            <h1 className="text-xl font-bold text-slate-900">Ya completaste tu diagnóstico inicial</h1>
            <Link
              to={DESTINO_TRAS_DIAGNOSTICO}
              className="mt-4 inline-block rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
            >
              Continuar
            </Link>
          </section>
        ) : (
          datos?.cuestionario &&
          usuario && (
            <FormularioDiagnostico
              key={datos.cuestionario.id}
              cuestionario={datos.cuestionario}
              usuario={usuario}
              alRecargar={() => void recargar()}
            />
          )
        )}
      </EstadoContenedor>
    </MarcoDiagnostico>
  );
}
