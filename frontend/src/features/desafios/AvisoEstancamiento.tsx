import { Link } from "react-router-dom";

import type { MensajeMotor } from "../../api/tiposDesafios";

/** R6: aviso de estancamiento. Con enlace lleva a los desafíos del concepto previo; sin él solo deriva (docente o material). */
export default function AvisoEstancamiento({ mensaje }: { mensaje: MensajeMotor }) {
  return (
    <div role="status" className="mt-3 rounded-lg border border-amber-300 bg-white p-3 text-amber-900">
      <p className="text-sm">{mensaje.texto}</p>
      {mensaje.enlace && (
        <Link to={mensaje.enlace} className="mt-1 inline-block text-sm font-semibold underline">
          Practicar el concepto previo
        </Link>
      )}
    </div>
  );
}
