import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ErrorApi } from "../../api/cliente";
import { useAuth } from "../../app/AuthContext";
import { destinoTrasLogin } from "../../app/destinos";
import CampoTexto from "../../components/CampoTexto";
import { mostrarToast } from "../../components/Toasts";
import {
  Errores,
  juntarErrores,
  validarContrasenaNueva,
  validarCorreo,
  validarNombre,
  validarObligatorio,
} from "./validaciones";

export default function RegistroPage() {
  const { registrar, login } = useAuth();
  const navigate = useNavigate();
  const [nombre, setNombre] = useState("");
  const [correo, setCorreo] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [errores, setErrores] = useState<Errores>({});
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setErrorGeneral(null);
    const locales = juntarErrores({
      nombre: validarNombre(nombre),
      correo: validarCorreo(correo),
      contrasena: validarContrasenaNueva(contrasena),
      confirmacion:
        validarObligatorio(confirmacion, "Repite tu contraseña.") ??
        (confirmacion !== contrasena ? "Las contraseñas no coinciden." : null),
    });
    setErrores(locales);
    if (Object.keys(locales).length) return;

    setEnviando(true);
    try {
      await registrar(nombre.trim(), correo.trim(), contrasena);
    } catch (err) {
      if (err instanceof ErrorApi) {
        const campos = { ...err.detalles };
        if (err.status === 409) campos.correo = err.mensaje;
        else if (!Object.keys(campos).length) setErrorGeneral(err.mensaje);
        setErrores(campos);
      } else {
        setErrorGeneral("Ocurrió un problema inesperado. Inténtalo de nuevo en unos minutos.");
      }
      setEnviando(false);
      return;
    }

    try {
      const usuario = await login(correo.trim(), contrasena);
      mostrarToast({ tipo: "exito", mensaje: "¡Cuenta creada! Bienvenido/a." });
      navigate(destinoTrasLogin(usuario), { replace: true });
    } catch {
      navigate("/login", { replace: true, state: { mensaje: "Tu cuenta fue creada. Inicia sesión para continuar." } });
    }
  };

  return (
    <main className="mx-auto mt-10 w-full max-w-md px-4 pb-10">
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-bold text-slate-900">Crear cuenta</h1>
        <p className="mt-1 text-sm text-slate-600">Regístrate como estudiante para empezar.</p>

        {errorGeneral && (
          <p role="alert" className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            {errorGeneral}
          </p>
        )}

        <form onSubmit={enviar} noValidate className="mt-4 space-y-4">
          <CampoTexto etiqueta="Nombre" autoComplete="name" valor={nombre} alCambiar={setNombre} error={errores.nombre} />
          <CampoTexto etiqueta="Correo" type="email" autoComplete="email" valor={correo} alCambiar={setCorreo} error={errores.correo} />
          <CampoTexto
            etiqueta="Contraseña"
            type="password"
            autoComplete="new-password"
            valor={contrasena}
            alCambiar={setContrasena}
            error={errores.contrasena}
            ayuda="Mínimo 8 caracteres, con al menos una letra y un número."
          />
          <CampoTexto
            etiqueta="Repite la contraseña"
            type="password"
            autoComplete="new-password"
            valor={confirmacion}
            alCambiar={setConfirmacion}
            error={errores.confirmacion}
          />
          <button
            type="submit"
            disabled={enviando}
            className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
          >
            {enviando ? "Creando cuenta…" : "Crear cuenta"}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-slate-600">
          ¿Ya tienes cuenta?{" "}
          <Link to="/login" className="font-medium text-indigo-700 underline">
            Inicia sesión
          </Link>
        </p>
      </div>
    </main>
  );
}
