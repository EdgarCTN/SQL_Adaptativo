import { Link } from "react-router-dom";

import type { ResultadoOmision as Resultado } from "../../api/tiposDesafios";
import AvisoNivel from "./AvisoNivel";
import { ETIQUETA_DIFICULTAD } from "./formatos";

/** Qué pasó al omitir: aviso de nivel (R8), desafío más básico sugerido (R8) y desafío de verificación (R7). */
export default function ResultadoOmision({ resultado }: { resultado: Resultado }) {
  const sugerencia = resultado.mensajes.find((m) => m.tipo === "sugerencia");
  return (
    <section role="status" className="mt-4 rounded-xl border border-indigo-200 bg-indigo-50 p-4 text-indigo-900">
      <h2 className="text-base font-semibold">Desafío omitido</h2>
      <p className="mt-1 text-sm">{resultado.mensaje}</p>

      {resultado.ajuste_nivel && <AvisoNivel ajuste={resultado.ajuste_nivel} />}

      {resultado.sugerido && (
        <div className="mt-3 rounded-lg border border-indigo-300 bg-white p-3 text-sm">
          <p>{sugerencia?.texto ?? "Te sugiero practicar antes un desafío más básico de este concepto."}</p>
          <Link to={`/desafios/${resultado.sugerido.id}`} className="mt-1 inline-block font-semibold underline">
            Ir a «{resultado.sugerido.titulo}» ({ETIQUETA_DIFICULTAD[resultado.sugerido.dificultad]})
          </Link>
        </div>
      )}

      {resultado.verificacion && (
        <div className="mt-3 rounded-lg border border-indigo-300 bg-white p-3 text-sm">
          <p>{resultado.verificacion.mensaje}</p>
          <Link to={`/desafios/${resultado.verificacion.desafio_id}`} className="mt-1 inline-block font-semibold underline">
            Ir al desafío de verificación: «{resultado.verificacion.titulo}» ({ETIQUETA_DIFICULTAD[resultado.verificacion.dificultad]})
          </Link>
        </div>
      )}

      <Link
        to="/desafios"
        className="mt-4 inline-block rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
      >
        Ver más desafíos
      </Link>
    </section>
  );
}
