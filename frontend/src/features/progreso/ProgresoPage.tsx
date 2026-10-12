import { Link } from "react-router-dom";

import { obtenerResumenProgreso } from "../../api/progreso";
import type { ResumenProgreso } from "../../api/tiposProgreso";
import { useCarga } from "../../api/useCarga";
import EstadoContenedor from "../../components/EstadoContenedor";

const TIPOS_AYUDA: { tipo: "AY1" | "AY2" | "AY3" | "AY4"; descripcion: string }[] = [
  { tipo: "AY1", descripcion: "Pista sin código" },
  { tipo: "AY2", descripcion: "Ejemplo de otro contexto" },
  { tipo: "AY3", descripcion: "Plantilla para completar" },
  { tipo: "AY4", descripcion: "Solución explicada" },
];

function formatearFecha(iso: string): string {
  const f = new Date(iso);
  return Number.isNaN(f.getTime())
    ? ""
    : f.toLocaleString("es", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function Tarjeta({ titulo, valor, detalle }: { titulo: string; valor: string; detalle?: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="text-sm font-medium text-slate-600">{titulo}</p>
      <p className="mt-1 text-3xl font-bold text-slate-900">{valor}</p>
      {detalle && <p className="mt-1 text-xs text-slate-500">{detalle}</p>}
    </div>
  );
}

function Contenido({ datos }: { datos: ResumenProgreso }) {
  const { ayudas } = datos;
  return (
    <div className="space-y-6">
      {datos.sin_actividad && (
        <div role="status" className="rounded-xl border border-indigo-200 bg-indigo-50 p-4 text-sm text-indigo-900">
          <p>{datos.sugerencia ?? "Resuelve un desafío para empezar a ver tu progreso."}</p>
          <Link to="/desafios" className="mt-2 inline-block font-semibold underline">
            Ir a los desafíos
          </Link>
        </div>
      )}

      <section aria-label="Resumen" className="grid gap-3 sm:grid-cols-3">
        <Tarjeta
          titulo="Desafíos resueltos"
          valor={`${datos.desafios_resueltos} de ${datos.desafios_disponibles}`}
          detalle="No cuentan los que terminaron tras ver la solución completa."
        />
        <Tarjeta titulo="Ayudas usadas" valor={String(ayudas.total)} />
        <Tarjeta titulo="Desafíos abandonados" valor={String(datos.sesiones_abandonadas)} />
      </section>

      <section aria-labelledby="titulo-niveles">
        <h2 id="titulo-niveles" className="text-lg font-semibold text-slate-900">
          Nivel de ayuda por concepto
        </h2>
        <p className="mt-1 text-sm text-slate-600">
          Va de 0 a 3: mientras más alto, más apoyo recibes en ese tema. Se ajusta según cómo te va en los desafíos.
          {!datos.diagnostico_completado && " Aún no completas el diagnóstico, así que todos parten en 1."}
        </p>
        <div className="mt-2 overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">Concepto</th>
                <th scope="col" className="px-4 py-2 font-medium">Nivel de ayuda</th>
                <th scope="col" className="px-4 py-2 font-medium">Desafíos resueltos</th>
              </tr>
            </thead>
            <tbody>
              {datos.niveles.map((n) => (
                <tr key={n.codigo} className="border-t border-slate-100">
                  <td className="px-4 py-2 text-slate-900">{n.nombre}</td>
                  <td className="px-4 py-2">
                    <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-semibold text-indigo-800">NS {n.ns}</span>
                  </td>
                  <td className="px-4 py-2 text-slate-700">{n.desafios_resueltos}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="titulo-ayudas">
        <h2 id="titulo-ayudas" className="text-lg font-semibold text-slate-900">
          Ayudas usadas por tipo
        </h2>
        <div className="mt-2 overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-600">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">Tipo</th>
                <th scope="col" className="px-4 py-2 font-medium">Descripción</th>
                <th scope="col" className="px-4 py-2 font-medium">Veces</th>
              </tr>
            </thead>
            <tbody>
              {TIPOS_AYUDA.map(({ tipo, descripcion }) => (
                <tr key={tipo} className="border-t border-slate-100">
                  <td className="px-4 py-2 font-medium text-slate-900">{tipo}</td>
                  <td className="px-4 py-2 text-slate-700">{descripcion}</td>
                  <td className="px-4 py-2 text-slate-700">{ayudas[tipo]}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="titulo-cambios">
        <h2 id="titulo-cambios" className="text-lg font-semibold text-slate-900">
          Últimos cambios de nivel
        </h2>
        {datos.cambios_recientes.length === 0 ? (
          <p className="mt-2 rounded-xl border border-dashed border-slate-300 p-4 text-sm text-slate-500">
            Todavía no ha cambiado tu nivel de ayuda en ningún concepto.
          </p>
        ) : (
          <div className="mt-2 overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th scope="col" className="px-4 py-2 font-medium">Fecha</th>
                  <th scope="col" className="px-4 py-2 font-medium">Concepto</th>
                  <th scope="col" className="px-4 py-2 font-medium">Cambio</th>
                  <th scope="col" className="px-4 py-2 font-medium">Motivo</th>
                </tr>
              </thead>
              <tbody>
                {datos.cambios_recientes.map((c, i) => (
                  <tr key={`${c.fecha}-${i}`} className="border-t border-slate-100 align-top">
                    <td className="whitespace-nowrap px-4 py-2 text-slate-700">{formatearFecha(c.fecha)}</td>
                    <td className="px-4 py-2 text-slate-900">{c.concepto}</td>
                    <td className="whitespace-nowrap px-4 py-2 text-slate-700">
                      {c.ns_anterior} → {c.ns_nuevo} {c.ns_nuevo < c.ns_anterior ? "(menos ayuda)" : "(más apoyo)"}
                    </td>
                    <td className="px-4 py-2 text-slate-700">{c.texto}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

export default function ProgresoPage() {
  const { datos, cargando, error, recargar } = useCarga(obtenerResumenProgreso);
  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-bold text-slate-900">Mi progreso</h1>
      <p className="mt-1 text-sm text-slate-600">Un vistazo a lo que has resuelto y a cómo se ajusta tu nivel de ayuda.</p>
      <div className="mt-4" aria-busy={cargando}>
        <EstadoContenedor cargando={cargando && !datos} error={error} onReintentar={() => void recargar()}>
          {datos && <Contenido datos={datos} />}
        </EstadoContenedor>
      </div>
    </div>
  );
}
