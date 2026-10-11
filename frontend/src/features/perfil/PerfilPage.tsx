import { FormEvent, useState } from "react";

import { editarPerfil, verPerfil } from "../../api/auth";
import { ErrorApi } from "../../api/cliente";
import type { Usuario } from "../../api/tipos";
import { useCarga } from "../../api/useCarga";
import { useAuth } from "../../app/AuthContext";
import CampoTexto from "../../components/CampoTexto";
import EstadoContenedor from "../../components/EstadoContenedor";
import { mostrarToast } from "../../components/Toasts";
import {
  Errores,
  juntarErrores,
  validarContrasenaNueva,
  validarNombre,
  validarObligatorio,
} from "../auth/validaciones";

const MSG_INESPERADO = "Ocurrió un problema inesperado. Inténtalo de nuevo en unos minutos.";

function FormNombre({ usuario, alGuardar }: { usuario: Usuario; alGuardar: (u: Usuario) => void }) {
  const [nombre, setNombre] = useState(usuario.nombre);
  const [errores, setErrores] = useState<Errores>({});
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setErrorGeneral(null);
    const locales = juntarErrores({ nombre: validarNombre(nombre) });
    setErrores(locales);
    if (Object.keys(locales).length) return;
    setEnviando(true);
    try {
      const actualizado = await editarPerfil({ nombre: nombre.trim() });
      alGuardar(actualizado);
      mostrarToast({ tipo: "exito", mensaje: "Guardamos tu nombre." });
    } catch (err) {
      if (err instanceof ErrorApi) {
        setErrores(err.detalles);
        setErrorGeneral(Object.keys(err.detalles).length ? null : err.mensaje);
      } else setErrorGeneral(MSG_INESPERADO);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <form onSubmit={enviar} noValidate className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-900">Tus datos</h2>
      {errorGeneral && (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {errorGeneral}
        </p>
      )}
      <CampoTexto etiqueta="Nombre" autoComplete="name" valor={nombre} alCambiar={setNombre} error={errores.nombre} />
      <button
        type="submit"
        disabled={enviando}
        className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
      >
        {enviando ? "Guardando…" : "Guardar nombre"}
      </button>
    </form>
  );
}

function FormContrasena({ alGuardar }: { alGuardar: (u: Usuario) => void }) {
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [errores, setErrores] = useState<Errores>({});
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setErrorGeneral(null);
    const locales = juntarErrores({
      contrasena_actual: validarObligatorio(actual, "Escribe tu contraseña actual."),
      contrasena_nueva: validarContrasenaNueva(nueva),
      confirmacion:
        validarObligatorio(confirmacion, "Repite la contraseña nueva.") ??
        (confirmacion !== nueva ? "Las contraseñas no coinciden." : null),
    });
    setErrores(locales);
    if (Object.keys(locales).length) return;
    setEnviando(true);
    try {
      const actualizado = await editarPerfil({ contrasena_actual: actual, contrasena_nueva: nueva });
      alGuardar(actualizado);
      setActual("");
      setNueva("");
      setConfirmacion("");
      mostrarToast({ tipo: "exito", mensaje: "Tu contraseña se actualizó." });
    } catch (err) {
      if (err instanceof ErrorApi) {
        setErrores(err.detalles);
        setErrorGeneral(Object.keys(err.detalles).length ? null : err.mensaje);
      } else setErrorGeneral(MSG_INESPERADO);
    } finally {
      setEnviando(false);
    }
  };

  return (
    <form onSubmit={enviar} noValidate className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-900">Cambiar contraseña</h2>
      {errorGeneral && (
        <p role="alert" className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
          {errorGeneral}
        </p>
      )}
      <CampoTexto
        etiqueta="Contraseña actual"
        type="password"
        autoComplete="current-password"
        valor={actual}
        alCambiar={setActual}
        error={errores.contrasena_actual}
      />
      <CampoTexto
        etiqueta="Contraseña nueva"
        type="password"
        autoComplete="new-password"
        valor={nueva}
        alCambiar={setNueva}
        error={errores.contrasena_nueva}
        ayuda="Mínimo 8 caracteres, con al menos una letra y un número."
      />
      <CampoTexto
        etiqueta="Repite la contraseña nueva"
        type="password"
        autoComplete="new-password"
        valor={confirmacion}
        alCambiar={setConfirmacion}
        error={errores.confirmacion}
      />
      <button
        type="submit"
        disabled={enviando}
        className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
      >
        {enviando ? "Guardando…" : "Cambiar contraseña"}
      </button>
    </form>
  );
}

export default function PerfilPage() {
  const { actualizarUsuario } = useAuth();
  const { datos, cargando, error, recargar } = useCarga(verPerfil);

  const alGuardar = (u: Usuario) => {
    actualizarUsuario(u);
    void recargar();
  };

  const fecha = datos
    ? new Date(datos.creado_en).toLocaleDateString("es", { year: "numeric", month: "long", day: "numeric" })
    : "";

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="text-2xl font-bold text-slate-900">Mi perfil</h1>
      <EstadoContenedor cargando={cargando && !datos} error={error} vacio={!datos} onReintentar={() => void recargar()}>
        {datos && (
          <>
            <section className="rounded-xl border border-slate-200 bg-white p-5">
              <dl className="grid gap-3 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-slate-500">Correo</dt>
                  <dd className="break-all font-medium">{datos.correo}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Rol</dt>
                  <dd className="font-medium capitalize">{datos.rol}</dd>
                </div>
                <div>
                  <dt className="text-slate-500">Miembro desde</dt>
                  <dd className="font-medium">{fecha}</dd>
                </div>
              </dl>
            </section>
            <section className="rounded-xl border border-slate-200 bg-white p-5">
              <FormNombre key={datos.nombre} usuario={datos} alGuardar={alGuardar} />
            </section>
            <section className="rounded-xl border border-slate-200 bg-white p-5">
              <FormContrasena alGuardar={alGuardar} />
            </section>
          </>
        )}
      </EstadoContenedor>
    </div>
  );
}
