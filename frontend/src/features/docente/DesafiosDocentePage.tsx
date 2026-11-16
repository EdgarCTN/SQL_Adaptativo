import { useCallback, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { activarDesafio, desactivarDesafio, eliminarDesafio, listarDesafiosDocente, opcionesDocente } from "../../api/docente";
import { mensajeDe } from "../../api/cliente";
import type { DesafioFila } from "../../api/tiposDocente";
import { useCarga } from "../../api/useCarga";
import DialogoConfirmacion from "../../components/DialogoConfirmacion";
import EstadoContenedor from "../../components/EstadoContenedor";
import { mostrarToast } from "../../components/Toasts";
import { ETIQUETA_DIFICULTAD, formatearDuracion } from "../desafios/formatos";

const CLASE_SELECT = "rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm";

export default function DesafiosDocentePage() {
  const [params, setParams] = useSearchParams();
  const concepto = params.get("concepto") ?? "";
  const dificultad = params.get("dificultad") ?? "";
  const estado = params.get("estado") ?? "";
  const q = params.get("q") ?? "";
  const [texto, setTexto] = useState(q);
  const [pendiente, setPendiente] = useState<number | null>(null);
  const [aBorrar, setABorrar] = useState<DesafioFila | null>(null);
  const [borrando, setBorrando] = useState(false);

  const cargador = useCallback(() => listarDesafiosDocente({ concepto, dificultad, estado, q }), [concepto, dificultad, estado, q]);
  const { datos, cargando, error, recargar } = useCarga(cargador);
  const { datos: opciones } = useCarga(opcionesDocente);

  const poner = (clave: string, valor: string) => {
    const nuevos = new URLSearchParams(params);
    if (valor) nuevos.set(clave, valor);
    else nuevos.delete(clave);
    setParams(nuevos, { replace: true });
  };

  const alternar = async (d: DesafioFila) => {
    setPendiente(d.id);
    try {
      const r = d.activo ? await desactivarDesafio(d.id) : await activarDesafio(d.id);
      mostrarToast({ tipo: "exito", mensaje: r.mensaje });
      await recargar();
    } catch (e) {
      mostrarToast({ tipo: "error", mensaje: mensajeDe(e) });
    } finally {
      setPendiente(null);
    }
  };

  const borrar = async () => {
    if (!aBorrar) return;
    setBorrando(true);
    try {
      const r = await eliminarDesafio(aBorrar.id);
      mostrarToast({ tipo: "exito", mensaje: r.mensaje });
      setABorrar(null);
      await recargar();
    } catch (e) {
      mostrarToast({ tipo: "error", mensaje: mensajeDe(e) });
      setABorrar(null);
    } finally {
      setBorrando(false);
    }
  };

  const hayFiltros = !!(concepto || dificultad || estado || q);

  return (
    <div className="mx-auto max-w-5xl">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Banco de desafíos</h1>
          <p className="mt-1 text-sm text-slate-600">
            Crea y edita desafíos. Cada uno se valida con el sandbox antes de guardarse.
          </p>
        </div>
        <Link to="/docente/desafios/nuevo" className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700">
          Nuevo desafío
        </Link>
      </div>

      <form
        className="mt-4 flex flex-wrap items-end gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          poner("q", texto.trim());
        }}
        role="search"
        aria-label="Filtrar desafíos"
      >
        <div>
          <label htmlFor="f-q" className="block text-sm font-medium text-slate-700">
            Buscar por título
          </label>
          <input id="f-q" type="search" value={texto} onChange={(e) => setTexto(e.target.value)} maxLength={100} className={`${CLASE_SELECT} mt-1 w-52`} />
        </div>
        <div>
          <label htmlFor="f-concepto" className="block text-sm font-medium text-slate-700">
            Concepto
          </label>
          <select id="f-concepto" value={concepto} onChange={(e) => poner("concepto", e.target.value)} className={`${CLASE_SELECT} mt-1`}>
            <option value="">Todos</option>
            {opciones?.conceptos.map((c) => (
              <option key={c.codigo} value={c.codigo}>
                {c.nombre}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="f-dificultad" className="block text-sm font-medium text-slate-700">
            Dificultad
          </label>
          <select id="f-dificultad" value={dificultad} onChange={(e) => poner("dificultad", e.target.value)} className={`${CLASE_SELECT} mt-1`}>
            <option value="">Todas</option>
            {(["D1", "D2", "D3"] as const).map((d) => (
              <option key={d} value={d}>
                {ETIQUETA_DIFICULTAD[d]}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="f-estado" className="block text-sm font-medium text-slate-700">
            Estado
          </label>
          <select id="f-estado" value={estado} onChange={(e) => poner("estado", e.target.value)} className={`${CLASE_SELECT} mt-1`}>
            <option value="">Todos</option>
            <option value="activos">Activos</option>
            <option value="inactivos">Desactivados</option>
          </select>
        </div>
        <button type="submit" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50">
          Buscar
        </button>
        {hayFiltros && (
          <button
            type="button"
            onClick={() => {
              setTexto("");
              setParams({}, { replace: true });
            }}
            className="rounded-lg px-3 py-1.5 text-sm font-medium text-indigo-700 underline"
          >
            Quitar filtros
          </button>
        )}
      </form>

      <div className="mt-4" aria-busy={cargando}>
        <EstadoContenedor
          cargando={cargando && !datos}
          error={error}
          vacio={!!datos && datos.total === 0}
          mensajeVacio={hayFiltros ? "Ningún desafío coincide con los filtros." : "Todavía no hay desafíos en el banco. Crea el primero."}
          onReintentar={() => void recargar()}
        >
          <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
            <table className="min-w-full text-left text-sm">
              <caption className="sr-only">Desafíos del banco</caption>
              <thead className="bg-slate-50 text-xs uppercase text-slate-600">
                <tr>
                  <th scope="col" className="px-3 py-2">Título</th>
                  <th scope="col" className="px-3 py-2">Concepto</th>
                  <th scope="col" className="px-3 py-2">Dificultad</th>
                  <th scope="col" className="px-3 py-2">Tiempo ref.</th>
                  <th scope="col" className="px-3 py-2">Estado</th>
                  <th scope="col" className="px-3 py-2">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {datos?.desafios.map((d) => (
                  <tr key={d.id} className={d.activo ? "" : "bg-slate-50 text-slate-500"}>
                    <th scope="row" className="px-3 py-2 font-medium">
                      {d.titulo}
                    </th>
                    <td className="px-3 py-2">{d.concepto.nombre}</td>
                    <td className="whitespace-nowrap px-3 py-2">{ETIQUETA_DIFICULTAD[d.dificultad]}</td>
                    <td className="whitespace-nowrap px-3 py-2">{formatearDuracion(d.tiempo_referencia_seg)}</td>
                    <td className="px-3 py-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${d.activo ? "bg-green-100 text-green-900" : "bg-slate-200 text-slate-700"}`}>
                        {d.activo ? "Activo" : "Desactivado"}
                      </span>
                      <span className="mt-1 block text-xs text-slate-500">
                        {d.n_sesiones === 0 ? "Sin sesiones" : `${d.n_sesiones} sesión${d.n_sesiones === 1 ? "" : "es"}`}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap gap-2">
                        <Link to={`/docente/desafios/${d.id}`} aria-label={`Editar ${d.titulo}`} className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50">
                          Editar
                        </Link>
                        <button
                          type="button"
                          disabled={pendiente === d.id}
                          onClick={() => void alternar(d)}
                          aria-label={`${d.activo ? "Desactivar" : "Activar"} ${d.titulo}`}
                          className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                        >
                          {pendiente === d.id ? "Un momento…" : d.activo ? "Desactivar" : "Activar"}
                        </button>
                        {d.n_sesiones === 0 && (
                          <button
                            type="button"
                            onClick={() => setABorrar(d)}
                            aria-label={`Eliminar ${d.titulo}`}
                            className="rounded-lg border border-red-300 px-2.5 py-1 text-xs font-medium text-red-700 hover:bg-red-50"
                          >
                            Eliminar
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            Un desafío con sesiones no se elimina: se desactiva, deja de verse para los estudiantes y su historial se conserva.
          </p>
        </EstadoContenedor>
      </div>

      {aBorrar && (
        <DialogoConfirmacion
          titulo="¿Eliminar este desafío?"
          mensaje={`«${aBorrar.titulo}» se borrará del banco. Esta acción no se puede deshacer.`}
          etiquetaConfirmar="Eliminar"
          etiquetaCancelar="Cancelar"
          etiquetaOcupado="Eliminando…"
          ocupado={borrando}
          onConfirmar={() => void borrar()}
          onCancelar={() => setABorrar(null)}
        />
      )}
    </div>
  );
}
