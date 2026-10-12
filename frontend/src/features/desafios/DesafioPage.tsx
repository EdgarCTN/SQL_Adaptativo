import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";

import { abandonarDesafio, enviarIntento, iniciarDesafio, obtenerDesafio } from "../../api/desafios";
import { ErrorApi, MSG_INESPERADO, mensajeDe } from "../../api/cliente";
import type { DesafioDetalle, ResultadoIntento as Resultado, SesionResumen } from "../../api/tiposDesafios";
import { useCarga } from "../../api/useCarga";
import { useAuth } from "../../app/AuthContext";
import DialogoConfirmacion from "../../components/DialogoConfirmacion";
import EstadoContenedor from "../../components/EstadoContenedor";
import { mostrarToast } from "../../components/Toasts";
import { ETIQUETA_DIFICULTAD, formatearDuracion, textoAjusteNivel } from "./formatos";
import PanelAyuda from "./PanelAyuda";
import ResultadoIntento from "./ResultadoIntento";
import { useAyuda } from "./useAyuda";

const MAX_CODIGO = 4000;
const MSG_NO_DISPONIBLE = "Este desafío no está disponible por ahora. Puedes elegir otro de la lista.";
const MSG_VACIO = "Escribe tu consulta antes de enviar.";

type Carga = { desafio: DesafioDetalle } | { noDisponible: string };

const claveBorrador = (usuarioId: number, desafioId: number) => `desafio:codigo:${usuarioId}:${desafioId}`;
function leerBorrador(clave: string): string {
  try {
    return sessionStorage.getItem(clave) ?? "";
  } catch {
    return "";
  }
}
function guardarBorrador(clave: string, codigo: string): void {
  try {
    if (codigo) sessionStorage.setItem(clave, codigo);
    else sessionStorage.removeItem(clave);
  } catch {
    /* sin almacenamiento: el borrador solo vive en pantalla */
  }
}

function VolverConAviso({ mensaje }: { mensaje: string }) {
  useEffect(() => {
    mostrarToast({ id: "desafio-no-disponible", tipo: "info", mensaje });
  }, [mensaje]);
  return <Navigate to="/desafios" replace />;
}

export default function DesafioPage() {
  const { id: idTexto } = useParams();
  const id = Number(idTexto);
  const idValido = Number.isInteger(id) && id > 0;

  const cargador = useCallback(async (): Promise<Carga> => {
    if (!idValido) return { noDisponible: MSG_NO_DISPONIBLE };
    try {
      return { desafio: await obtenerDesafio(id) };
    } catch (e) {
      if (e instanceof ErrorApi && e.status === 404) return { noDisponible: e.mensaje };
      throw e;
    }
  }, [id, idValido]);
  const { datos, cargando, error, recargar } = useCarga(cargador);

  if (datos && "noDisponible" in datos) return <VolverConAviso mensaje={datos.noDisponible} />;

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/desafios" className="text-sm font-medium text-indigo-700 underline">
        ← Volver a los desafíos
      </Link>
      <div className="mt-3">
        <EstadoContenedor cargando={cargando && !datos} error={error} onReintentar={() => void recargar()}>
          {datos && "desafio" in datos && (
            <DetalleDesafio key={datos.desafio.id} inicial={datos.desafio} alRecargar={() => void recargar()} />
          )}
        </EstadoContenedor>
      </div>
    </div>
  );
}

interface PropsDetalle {
  inicial: DesafioDetalle;
  alRecargar: () => void;
}

function DetalleDesafio({ inicial, alRecargar }: PropsDetalle) {
  const navigate = useNavigate();
  const { usuario } = useAuth();
  const desafioId = inicial.id;
  const clave = claveBorrador(usuario?.id ?? 0, desafioId);

  const [sesion, setSesion] = useState<SesionResumen | null>(inicial.sesion_en_curso);
  const [resuelto, setResuelto] = useState(false);
  const [codigo, setCodigo] = useState(() => (inicial.sesion_en_curso ? leerBorrador(clave) : ""));
  const [intento, setIntento] = useState<Resultado | null>(null);
  const [iniciando, setIniciando] = useState(false);
  const [enviando, setEnviando] = useState(false);
  const [errorCodigo, setErrorCodigo] = useState<string | null>(null);
  const [errorEnvio, setErrorEnvio] = useState<string | null>(null);
  const [confirmando, setConfirmando] = useState(false);
  const [abandonando, setAbandonando] = useState(false);

  // Si la pantalla recarga datos del servidor (p. ej. tras un 409), se vuelve a sincronizar el estado.
  const primera = useRef(true);
  useEffect(() => {
    if (primera.current) {
      primera.current = false;
      return;
    }
    setSesion(inicial.sesion_en_curso);
    setResuelto(false);
    setIntento(null);
    setErrorEnvio(null);
  }, [inicial]);

  const noDisponible = (mensaje: string) => {
    mostrarToast({ id: "desafio-no-disponible", tipo: "info", mensaje });
    navigate("/desafios", { replace: true });
  };

  const ayuda = useAyuda({
    desafioId,
    sesionId: sesion?.sesion_id ?? null,
    usuarioId: usuario?.id ?? 0,
    alNoDisponible: noDisponible,
    alRecargar,
  });
  // Al entregarse la solución completa (AY4) el desafío queda como no resuelto.
  const ay4 = ayuda.ayudas.find((a) => a.tipo_ayuda === "AY4");
  const marcadoNR = !!ay4;

  const comenzar = async () => {
    if (iniciando) return;
    setIniciando(true);
    try {
      const r = await iniciarDesafio(desafioId);
      guardarBorrador(clave, "");
      setCodigo("");
      setIntento(null);
      setResuelto(false);
      setSesion({ sesion_id: r.sesion_id, inicio: r.inicio, intentos_realizados: r.intentos_realizados });
      if (r.reanudada) mostrarToast({ tipo: "info", mensaje: "Retomaste tu desafío en curso." });
    } catch (e) {
      if (e instanceof ErrorApi && e.status === 404) noDisponible(e.mensaje);
      else mostrarToast({ tipo: "error", mensaje: mensajeDe(e) });
    } finally {
      setIniciando(false);
    }
  };

  const cambiarCodigo = (valor: string) => {
    setCodigo(valor);
    guardarBorrador(clave, valor);
    if (errorCodigo) setErrorCodigo(null);
  };

  const enviar = async () => {
    if (enviando || !sesion || resuelto) return;
    if (!codigo.trim()) {
      setErrorCodigo(MSG_VACIO);
      return;
    }
    setEnviando(true);
    setErrorCodigo(null);
    setErrorEnvio(null);
    try {
      const r = await enviarIntento(desafioId, codigo);
      setIntento(r);
      setSesion({ ...sesion, intentos_realizados: r.numero });
      if (r.desafio_resuelto) {
        setResuelto(true);
        guardarBorrador(clave, "");
      }
    } catch (e) {
      if (!(e instanceof ErrorApi)) setErrorEnvio(MSG_INESPERADO);
      else if (e.status === 422) setErrorCodigo(e.detalles.codigo ?? e.mensaje);
      else if (e.status === 404) noDisponible(e.mensaje);
      else if (e.status === 409) {
        mostrarToast({ tipo: "info", mensaje: e.mensaje });
        alRecargar();
      } else setErrorEnvio(e.mensaje);
    } finally {
      setEnviando(false);
    }
  };

  const confirmarAbandono = async () => {
    setAbandonando(true);
    try {
      const r = await abandonarDesafio(desafioId);
      guardarBorrador(clave, "");
      ayuda.descartar();
      mostrarToast({ tipo: "info", mensaje: r.ajuste_nivel ? `${r.mensaje} ${textoAjusteNivel(r.ajuste_nivel)} ${r.ajuste_nivel.motivo}` : r.mensaje });
      navigate("/desafios", { replace: true });
    } catch (e) {
      setAbandonando(false);
      setConfirmando(false);
      if (e instanceof ErrorApi && e.status === 404) noDisponible(e.mensaje);
      else if (e instanceof ErrorApi && e.status === 409) {
        mostrarToast({ tipo: "info", mensaje: e.mensaje });
        alRecargar();
      } else mostrarToast({ tipo: "error", mensaje: mensajeDe(e) });
    }
  };

  const yaResueltoAntes = !sesion && inicial.estado === "resuelto";

  return (
    <article>
      <header>
        <h1 className="text-2xl font-bold text-slate-900">{inicial.titulo}</h1>
        <p className="mt-1 flex flex-wrap gap-x-3 text-sm text-slate-600">
          <span>{inicial.concepto.nombre}</span>
          <span>{ETIQUETA_DIFICULTAD[inicial.dificultad]}</span>
          <span>Tiempo de referencia: {formatearDuracion(inicial.tiempo_referencia_seg)}</span>
          {marcadoNR && <span className="font-semibold text-amber-800">✗ Se marcará como no resuelto</span>}
        </p>
      </header>

      <section className="mt-4 rounded-xl border border-slate-200 bg-white p-4" aria-labelledby="titulo-enunciado">
        <h2 id="titulo-enunciado" className="text-base font-semibold text-slate-900">
          Enunciado
        </h2>
        <p className="mt-1 whitespace-pre-line text-sm text-slate-800">{inicial.enunciado}</p>
        {inicial.recursos.length > 0 && (
          <>
            <h3 className="mt-3 text-sm font-semibold text-slate-900">Recursos</h3>
            <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-slate-700">
              {inicial.recursos.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </>
        )}
      </section>

      <details open className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
        <summary className="cursor-pointer text-base font-semibold text-slate-900">Esquema de la base de datos</summary>
        <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-900 p-3 font-mono text-xs text-slate-100">
          {inicial.esquema_sql}
        </pre>
      </details>

      {!sesion && (
        <section className="mt-4 rounded-xl border border-indigo-200 bg-indigo-50 p-4">
          {yaResueltoAntes ? (
            <p className="text-sm text-indigo-900">
              <strong>Ya resolviste este desafío.</strong> Puedes elegir otro o intentarlo de nuevo.
            </p>
          ) : (
            <p className="text-sm text-indigo-900">
              Cuando estés listo, pulsa «Comenzar desafío». Al comenzar se inicia tu sesión y se registran tus intentos.
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => void comenzar()}
              disabled={iniciando}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
            >
              {iniciando ? "Iniciando…" : yaResueltoAntes ? "Intentarlo de nuevo" : "Comenzar desafío"}
            </button>
            {yaResueltoAntes && (
              <Link
                to="/desafios"
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                Ver otros desafíos
              </Link>
            )}
          </div>
        </section>
      )}

      {sesion && (
        <form
          className="mt-4"
          noValidate
          onSubmit={(e) => {
            e.preventDefault();
            void enviar();
          }}
        >
          <label htmlFor="consulta" className="block text-sm font-semibold text-slate-900">
            Tu consulta SQL
          </label>
          <textarea
            id="consulta"
            value={codigo}
            onChange={(e) => cambiarCodigo(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                void enviar();
              }
            }}
            rows={9}
            maxLength={MAX_CODIGO}
            readOnly={resuelto || enviando}
            spellCheck={false}
            autoCapitalize="off"
            autoCorrect="off"
            aria-invalid={errorCodigo ? true : undefined}
            aria-describedby={errorCodigo ? "consulta-ayuda consulta-error" : "consulta-ayuda"}
            placeholder="SELECT ..."
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white p-3 font-mono text-sm text-slate-900 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-200 read-only:bg-slate-50"
          />
          <p id="consulta-ayuda" className="mt-1 flex justify-between gap-2 text-xs text-slate-500">
            <span>Tus consultas se ejecutan en SQLite. Ctrl + Enter para enviar.</span>
            <span>
              {codigo.length}/{MAX_CODIGO}
            </span>
          </p>
          {errorCodigo && (
            <p id="consulta-error" role="alert" className="mt-1 text-sm text-red-700">
              {errorCodigo}
            </p>
          )}
          {errorEnvio && (
            <p role="alert" className="mt-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              {errorEnvio} Tu consulta sigue en el cuadro; puedes volver a enviarla.
            </p>
          )}

          <div className="mt-3 flex flex-wrap items-center gap-2">
            {resuelto ? (
              <Link
                to="/desafios"
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
              >
                Ver más desafíos
              </Link>
            ) : (
              <>
                <button
                  type="submit"
                  disabled={enviando || ayuda.pidiendo || !codigo.trim()}
                  className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60"
                >
                  {enviando ? "Enviando…" : "Enviar"}
                </button>
                <button
                  type="button"
                  onClick={() => setConfirmando(true)}
                  disabled={enviando || ayuda.pidiendo}
                  className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                >
                  Abandonar
                </button>
              </>
            )}
            <span className="text-xs text-slate-500">
              Intentos en esta sesión: {sesion.intentos_realizados}
            </span>
          </div>
        </form>
      )}

      <div aria-live="polite" className="mt-4">
        {intento && <ResultadoIntento intento={intento} />}
      </div>

      {marcadoNR && (
        <p role="status" className="mt-4 rounded-xl border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          {ay4?.aviso ?? "Este desafío se marcará como no resuelto."}
        </p>
      )}

      {sesion && (
        <PanelAyuda
          ayudas={ayuda.ayudas}
          activo={!resuelto}
          pidiendo={ayuda.pidiendo}
          deshabilitado={enviando}
          errorAyuda={ayuda.errorAyuda}
          avisoSolo={ayuda.avisoSolo}
          valorando={ayuda.valorando}
          onPedir={ayuda.pedir}
          onValorar={(id, v) => void ayuda.valorar(id, v)}
        />
      )}

      {confirmando && (
        <DialogoConfirmacion
          titulo="¿Abandonar este desafío?"
          mensaje="Se cerrará tu sesión y el desafío quedará registrado como no resuelto. Podrás volver a intentarlo cuando quieras."
          etiquetaConfirmar="Sí, abandonar"
          etiquetaCancelar="Seguir intentando"
          ocupado={abandonando}
          onConfirmar={() => void confirmarAbandono()}
          onCancelar={() => setConfirmando(false)}
        />
      )}
    </article>
  );
}
