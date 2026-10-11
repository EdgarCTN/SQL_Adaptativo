import { FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { ErrorApi } from "../../api/cliente";
import { useAuth } from "../../app/AuthContext";
import { destinoTrasLogin } from "../../app/destinos";
import CampoTexto from "../../components/CampoTexto";
import { Errores, juntarErrores, validarCorreo, validarObligatorio } from "./validaciones";

interface EstadoNavegacion {
  mensaje?: string;
  desde?: string;
}

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const estado = (useLocation().state ?? {}) as EstadoNavegacion;
  const [correo, setCorreo] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [errores, setErrores] = useState<Errores>({});
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    setErrorGeneral(null);
    const locales = juntarErrores({
      correo: validarCorreo(correo),
      contrasena: validarObligatorio(contrasena, "Escribe tu contraseña."),
    });
    setErrores(locales);
    if (Object.keys(locales).length) return;

    setEnviando(true);
    try {
      const usuario = await login(correo.trim(), contrasena);
      const desde = estado.desde && estado.desde.startsWith("/") && !["/login", "/registro"].includes(estado.desde) ? estado.desde : null;
      const destino = destinoTrasLogin(usuario);
      navigate(destino === "/consentimiento" ? destino : (desde ?? destino), { replace: true });
    } catch (err) {
      if (err instanceof ErrorApi) {
        setErrores(err.detalles);
        setErrorGeneral(Object.keys(err.detalles).length ? null : err.mensaje);
      } else {
        setErrorGeneral("Ocurrió un problema inesperado. Inténtalo de nuevo en unos minutos.");
      }
    } finally {
      setEnviando(false);
    }
  };

  return (
    <main className="mx-auto mt-12 w-full max-w-md px-4">
      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-2xl font-bold text-slate-900">Iniciar sesión</h1>
        <p className="mt-1 text-sm text-slate-600">Entra para practicar SQL con desafíos a tu medida.</p>

        {estado.mensaje && (
          <p role="status" className="mt-4 rounded-lg border border-indigo-200 bg-indigo-50 p-3 text-sm text-indigo-900">
            {estado.mensaje}
          </p>
        )}
        {errorGeneral && (
          <p role="alert" className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
            {errorGeneral}
          </p>
        )}

        <form onSubmit={enviar} noValidate className="mt-4 space-y-4">
          <CampoTexto etiqueta="Correo" type="email" autoComplete="email" valor={correo} alCambiar={setCorreo} error={errores.correo} />
          <CampoTexto
            etiqueta="Contraseña"
            type="password"
            autoComplete="current-password"
            valor={contrasena}
            alCambiar={setContrasena}
            error={errores.contrasena}
          />
          <button
            type="submit"
            disabled={enviando}
            className="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
          >
            {enviando ? "Entrando…" : "Entrar"}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-slate-600">
          ¿No tienes cuenta?{" "}
          <Link to="/registro" className="font-medium text-indigo-700 underline">
            Regístrate
          </Link>
        </p>
      </div>
    </main>
  );
}
