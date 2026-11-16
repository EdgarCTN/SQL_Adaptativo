import { useCallback, useId, useState } from "react";

import { activarUsuario, cambiarRolUsuario, desactivarUsuario, listarUsuarios } from "../../api/admin";
import { mensajeDe } from "../../api/cliente";
import type { Rol } from "../../api/tipos";
import type { UsuarioAdmin } from "../../api/tiposAdmin";
import { useCarga } from "../../api/useCarga";
import { useAuth } from "../../app/AuthContext";
import DialogoConfirmacion from "../../components/DialogoConfirmacion";
import EstadoContenedor from "../../components/EstadoContenedor";
import { mostrarToast } from "../../components/Toasts";
import { formatearFechaCorta } from "../progreso/fechas";

const TAM = 15;
const ROLES: Rol[] = ["estudiante", "docente", "administrador"];
const ETIQUETA_ROL: Record<Rol, string> = { estudiante: "Estudiante", docente: "Docente", administrador: "Administrador" };
const CLASE_CAMPO = "rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-900";
const CLASE_BOTON = "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50";

type Accion = { tipo: "rol"; usuario: UsuarioAdmin; rol: Rol } | { tipo: "desactivar"; usuario: UsuarioAdmin };

export default function UsuariosPage() {
  const id = useId();
  const { usuario: yo } = useAuth();
  const [texto, setTexto] = useState("");
  const [q, setQ] = useState("");
  const [rol, setRol] = useState<Rol | "">("");
  const [pagina, setPagina] = useState(1);
  const [accion, setAccion] = useState<Accion | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [pendiente, setPendiente] = useState<number | null>(null);

  const cargador = useCallback(() => listarUsuarios({ q, rol, pagina, tam: TAM }), [q, rol, pagina]);
  const { datos, cargando, error, recargar } = useCarga(cargador);

  const hayFiltros = Boolean(q || rol);
  const sinResultados = datos !== null && datos.total === 0;

  const buscar = (e: React.FormEvent) => {
    e.preventDefault();
    setQ(texto.trim());
    setPagina(1);
  };
  const limpiar = () => {
    setTexto("");
    setQ("");
    setRol("");
    setPagina(1);
  };

  const confirmar = async () => {
    if (!accion) return;
    setOcupado(true);
    try {
      const r =
        accion.tipo === "rol"
          ? await cambiarRolUsuario(accion.usuario.id, accion.rol)
          : await desactivarUsuario(accion.usuario.id);
      mostrarToast({ tipo: "exito", mensaje: r.mensaje });
    } catch (e) {
      mostrarToast({ tipo: "error", mensaje: mensajeDe(e) });
    } finally {
      setOcupado(false);
      setAccion(null);
      await recargar(); // también tras un error: la lista vuelve a reflejar lo que hay en el servidor
    }
  };

  const activar = async (u: UsuarioAdmin) => {
    setPendiente(u.id);
    try {
      const r = await activarUsuario(u.id);
      mostrarToast({ tipo: "exito", mensaje: r.mensaje });
    } catch (e) {
      mostrarToast({ tipo: "error", mensaje: mensajeDe(e) });
    } finally {
      setPendiente(null);
      await recargar();
    }
  };

  return (
    <div className="mx-auto max-w-5xl">
      <h1 className="text-2xl font-bold text-slate-900">Usuarios</h1>
      <p className="mt-1 text-sm text-slate-600">
        Asigna el rol de cada cuenta y activa o desactiva el acceso. Los cambios de rol quedan registrados en la auditoría.
      </p>

      <form className="mt-4 flex flex-wrap items-end gap-3" onSubmit={buscar} role="search" aria-label="Buscar usuarios">
        <div>
          <label htmlFor={`${id}-q`} className="block text-sm font-medium text-slate-700">
            Buscar por nombre o correo
          </label>
          <input
            id={`${id}-q`}
            type="search"
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            maxLength={100}
            className={`${CLASE_CAMPO} mt-1 w-64`}
          />
        </div>
        <div>
          <label htmlFor={`${id}-rol`} className="block text-sm font-medium text-slate-700">
            Rol
          </label>
          <select
            id={`${id}-rol`}
            value={rol}
            onChange={(e) => {
              setRol(e.target.value as Rol | "");
              setPagina(1);
            }}
            className={`${CLASE_CAMPO} mt-1`}
          >
            <option value="">Todos</option>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ETIQUETA_ROL[r]}
              </option>
            ))}
          </select>
        </div>
        <button type="submit" className={CLASE_BOTON}>
          Buscar
        </button>
        {(hayFiltros || texto) && (
          <button type="button" onClick={limpiar} className="rounded-lg px-3 py-1.5 text-sm font-medium text-indigo-700 underline">
            Quitar filtros
          </button>
        )}
      </form>

      <div className="mt-4" aria-busy={cargando}>
        <EstadoContenedor
          cargando={cargando && !datos}
          error={error}
          onReintentar={() => void recargar()}
          vacio={sinResultados}
          mensajeVacio={hayFiltros ? "Ningún usuario coincide con la búsqueda." : "Todavía no hay usuarios registrados."}
        >
          {datos && datos.total > 0 && (
            <>
              <p role="status" className="mb-2 text-sm text-slate-600">
                {datos.total} {datos.total === 1 ? "usuario" : "usuarios"} · página {datos.pagina} de {datos.paginas}
              </p>
              <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
                <table className="min-w-full text-left text-sm">
                  <caption className="sr-only">Usuarios de la plataforma</caption>
                  <thead className="bg-slate-50 text-xs uppercase text-slate-600">
                    <tr>
                      <th scope="col" className="px-3 py-2">Nombre</th>
                      <th scope="col" className="px-3 py-2">Correo</th>
                      <th scope="col" className="px-3 py-2">Rol</th>
                      <th scope="col" className="px-3 py-2">Estado</th>
                      <th scope="col" className="px-3 py-2">Alta</th>
                      <th scope="col" className="px-3 py-2">Acciones</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {datos.usuarios.map((u) => {
                      const esYo = u.id === yo?.id;
                      return (
                        <tr key={u.id} className={u.activo ? "" : "bg-slate-50 text-slate-500"}>
                          <th scope="row" className="px-3 py-2 font-medium">
                            {u.nombre}
                            {esYo && <span className="ml-2 rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-semibold text-indigo-800">Tú</span>}
                          </th>
                          <td className="px-3 py-2">{u.correo}</td>
                          <td className="px-3 py-2">
                            <select
                              aria-label={`Rol de ${u.nombre}`}
                              value={u.rol}
                              disabled={esYo || ocupado || pendiente === u.id}
                              title={esYo ? "No puedes cambiar tu propio rol" : undefined}
                              onChange={(e) => setAccion({ tipo: "rol", usuario: u, rol: e.target.value as Rol })}
                              className={`${CLASE_CAMPO} disabled:opacity-60`}
                            >
                              {ROLES.map((r) => (
                                <option key={r} value={r}>
                                  {ETIQUETA_ROL[r]}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="px-3 py-2">
                            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${u.activo ? "bg-green-100 text-green-900" : "bg-slate-200 text-slate-700"}`}>
                              {u.activo ? "Activa" : "Desactivada"}
                            </span>
                          </td>
                          <td className="whitespace-nowrap px-3 py-2">{formatearFechaCorta(u.creado_en)}</td>
                          <td className="px-3 py-2">
                            {esYo ? (
                              <span className="text-xs text-slate-500">—</span>
                            ) : u.activo ? (
                              <button
                                type="button"
                                disabled={ocupado || pendiente === u.id}
                                onClick={() => setAccion({ tipo: "desactivar", usuario: u })}
                                aria-label={`Desactivar la cuenta de ${u.nombre}`}
                                className="rounded-lg border border-red-300 px-2.5 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-60"
                              >
                                Desactivar
                              </button>
                            ) : (
                              <button
                                type="button"
                                disabled={ocupado || pendiente === u.id}
                                onClick={() => void activar(u)}
                                aria-label={`Activar la cuenta de ${u.nombre}`}
                                className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                              >
                                {pendiente === u.id ? "Un momento…" : "Activar"}
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              {datos.paginas > 1 && (
                <nav aria-label="Paginación de usuarios" className="mt-3 flex items-center justify-between gap-3">
                  <button type="button" onClick={() => setPagina((p) => Math.max(1, p - 1))} disabled={datos.pagina <= 1 || cargando} className={CLASE_BOTON}>
                    ← Anterior
                  </button>
                  <span className="text-sm text-slate-600">
                    Página {datos.pagina} de {datos.paginas}
                  </span>
                  <button
                    type="button"
                    onClick={() => setPagina((p) => Math.min(datos.paginas, p + 1))}
                    disabled={datos.pagina >= datos.paginas || cargando}
                    className={CLASE_BOTON}
                  >
                    Siguiente →
                  </button>
                </nav>
              )}
              <p className="mt-2 text-xs text-slate-500">
                Siempre debe quedar al menos un administrador activo. El cambio de rol se ve en el menú de la persona al volver a la aplicación.
              </p>
            </>
          )}
        </EstadoContenedor>
      </div>

      {accion && (
        <DialogoConfirmacion
          titulo={accion.tipo === "rol" ? "¿Cambiar el rol?" : "¿Desactivar esta cuenta?"}
          mensaje={
            accion.tipo === "rol"
              ? `${accion.usuario.nombre} pasará de ${ETIQUETA_ROL[accion.usuario.rol].toLowerCase()} a ${ETIQUETA_ROL[accion.rol].toLowerCase()}. Sus permisos cambian de inmediato y su menú se actualiza al volver a la aplicación.`
              : `${accion.usuario.nombre} no podrá iniciar sesión hasta que vuelvas a activar la cuenta. Sus datos se conservan.`
          }
          etiquetaConfirmar={accion.tipo === "rol" ? "Cambiar rol" : "Desactivar"}
          etiquetaCancelar="Cancelar"
          etiquetaOcupado="Guardando…"
          ocupado={ocupado}
          onConfirmar={() => void confirmar()}
          onCancelar={() => setAccion(null)}
        />
      )}
    </div>
  );
}
