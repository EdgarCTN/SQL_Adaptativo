import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import {
  actualizarDesafio,
  borradorDe,
  borradorVacio,
  crearDesafio,
  cuerpoDe,
  obtenerDesafioDocente,
  opcionesDocente,
  validarDesafio,
} from "../../api/docente";
import { ErrorApi, mensajeDe } from "../../api/cliente";
import type { BorradorDesafio, DesafioDocente, OpcionesDocente, Problema, TipoAyuda } from "../../api/tiposDocente";
import { TIPOS_AYUDA } from "../../api/tiposDocente";
import { useCarga } from "../../api/useCarga";
import CampoTexto from "../../components/CampoTexto";
import DialogoConfirmacion from "../../components/DialogoConfirmacion";
import EstadoContenedor from "../../components/EstadoContenedor";
import { mostrarToast } from "../../components/Toasts";
import { ETIQUETA_DIFICULTAD } from "../desafios/formatos";
import { CampoArea, CampoSeleccion } from "./campos";
import { etiquetaCampo } from "./etiquetas";
import VistaPreviaDesafio from "./VistaPreviaDesafio";

const AYUDAS: Record<TipoAyuda, { titulo: string; guia: string; conCodigo: boolean }> = {
  AY1: { titulo: "AY1 · Pista", guia: "Orienta sin código ni palabras clave de SQL (SELECT, WHERE, JOIN…) y sin revelar la solución.", conCodigo: false },
  AY2: { titulo: "AY2 · Ejemplo en otro contexto", guia: "El código debe usar otras tablas y columnas distintas a las del desafío.", conCodigo: true },
  AY3: { titulo: "AY3 · Esqueleto para completar", guia: "El código lleva al menos dos espacios ___ y sus partes visibles coinciden, en orden, con la solución.", conCodigo: true },
  AY4: { titulo: "AY4 · Solución completa", guia: "El código debe ser una solución que el sandbox acepte.", conCodigo: true },
};

export default function FormularioDesafioPage() {
  const { id } = useParams();
  const idNum = id === undefined ? null : Number(id);
  const idValido = idNum === null || (Number.isInteger(idNum) && idNum > 0);
  const cargadorDesafio = useCallback(
    () => (idNum !== null && idValido ? obtenerDesafioDocente(idNum) : Promise.resolve<DesafioDocente | null>(null)),
    [idNum, idValido]
  );
  const opc = useCarga(opcionesDocente);
  const des = useCarga(cargadorDesafio);

  if (!idValido) {
    return <p role="alert" className="rounded-xl border border-red-200 bg-red-50 p-6 text-center text-sm text-red-800">No encontramos ese desafío en el banco.</p>;
  }
  const listo = !!opc.datos && (idNum === null || !!des.datos);
  return (
    <div className="mx-auto max-w-4xl">
      <Link to="/docente/desafios" className="text-sm font-medium text-indigo-700 underline">
        ← Volver al banco
      </Link>
      <div className="mt-3">
        <EstadoContenedor
          cargando={!listo && (opc.cargando || des.cargando)}
          error={listo ? null : opc.error || des.error}
          onReintentar={() => {
            void opc.recargar();
            void des.recargar();
          }}
        >
          {listo && opc.datos && <Formulario key={idNum ?? "nuevo"} opciones={opc.datos} desafio={des.datos} />}
        </EstadoContenedor>
      </div>
    </div>
  );
}

function Formulario({ opciones, desafio }: { opciones: OpcionesDocente; desafio: DesafioDocente | null }) {
  const navegar = useNavigate();
  const [b, setB] = useState<BorradorDesafio>(() =>
    desafio ? borradorDe(desafio, opciones.n_errores_tipicos) : borradorVacio(opciones.n_errores_tipicos)
  );
  const [problemas, setProblemas] = useState<Problema[]>([]);
  const [valido, setValido] = useState(false);
  const [ocupado, setOcupado] = useState<"validar" | "guardar" | null>(null);
  const [confirmar, setConfirmar] = useState<string | null>(null);
  const [vista, setVista] = useState(false);
  const [foco, setFoco] = useState(0);
  const resumen = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (foco > 0) resumen.current?.focus();
  }, [foco]);

  const cambiar = (parcial: Partial<BorradorDesafio>, campo?: string) => {
    setB((p) => ({ ...p, ...parcial }));
    setValido(false);
    if (campo) setProblemas((p) => p.filter((x) => x.campo !== campo));
  };
  const error = (campo: string) => problemas.find((p) => p.campo === campo)?.mensaje;

  const cambiarError = (i: number, parte: "descripcion" | "ejemplo", valor: string) =>
    cambiar({ errores_tipicos: b.errores_tipicos.map((e, k) => (k === i ? { ...e, [parte]: valor } : e)) }, `errores_tipicos.${i}.${parte}`);
  const cambiarAyuda = (t: TipoAyuda, parte: "mensaje" | "codigo_sql", valor: string) =>
    cambiar({ ayudas_respaldo: { ...b.ayudas_respaldo, [t]: { ...b.ayudas_respaldo[t], [parte]: valor } } }, `ayudas_respaldo.${t}.${parte}`);

  const validar = async () => {
    setOcupado("validar");
    try {
      const r = await validarDesafio(cuerpoDe(b), desafio?.id);
      setProblemas(r.problemas);
      setValido(r.valido);
      if (!r.valido) setFoco((f) => f + 1);
    } catch (e) {
      mostrarToast({ tipo: "error", mensaje: mensajeDe(e) });
    } finally {
      setOcupado(null);
    }
  };

  const guardar = async (confirmado = false) => {
    setOcupado("guardar");
    try {
      const cuerpo = cuerpoDe(b);
      if (desafio) await actualizarDesafio(desafio.id, cuerpo, confirmado);
      else await crearDesafio(cuerpo);
      mostrarToast({
        tipo: "exito",
        mensaje: desafio ? "Cambios guardados: el desafío pasó la validación." : "Desafío creado: pasó la validación y ya está disponible para los estudiantes.",
      });
      navegar("/docente/desafios");
    } catch (e) {
      if (e instanceof ErrorApi && e.status === 409 && desafio) {
        setConfirmar(e.mensaje); // cambia solución o setup de un desafío ya usado
      } else if (e instanceof ErrorApi && e.status === 422 && Object.keys(e.detalles).length > 0) {
        setProblemas(Object.entries(e.detalles).map(([campo, mensaje]) => ({ campo, mensaje })));
        setValido(false);
        setFoco((f) => f + 1);
      } else {
        mostrarToast({ tipo: "error", mensaje: mensajeDe(e) });
      }
    } finally {
      setOcupado(null);
    }
  };

  const tiempoPorDefecto = b.dificultad ? opciones.tiempos_referencia[b.dificultad] : undefined;
  const tiempoNum = Number.parseInt(b.tiempo_referencia_seg, 10);
  const concepto = opciones.conceptos.find((c) => c.codigo === b.concepto)?.nombre ?? "";

  return (
    <form
      noValidate
      onSubmit={(e) => {
        e.preventDefault();
        void guardar();
      }}
      aria-busy={ocupado !== null}
    >
      <h1 className="text-2xl font-bold text-slate-900">{desafio ? "Editar desafío" : "Nuevo desafío"}</h1>
      {desafio && !desafio.activo && (
        <p role="status" className="mt-2 rounded-lg border border-slate-300 bg-slate-100 p-2 text-sm text-slate-700">
          Este desafío está desactivado: los estudiantes no lo ven. Actívalo desde el banco.
        </p>
      )}
      {desafio && desafio.n_sesiones > 0 && (
        <p role="status" className="mt-2 rounded-lg border border-amber-300 bg-amber-50 p-2 text-sm text-amber-900">
          Este desafío ya tiene {desafio.n_sesiones} sesión{desafio.n_sesiones === 1 ? "" : "es"} de estudiantes. Si cambias la solución o el setup te pediremos confirmación.
        </p>
      )}

      <div ref={resumen} tabIndex={-1} className="outline-none">
        {problemas.length > 0 && (
          <div role="alert" className="mt-4 rounded-xl border border-red-300 bg-red-50 p-4 text-sm text-red-900">
            <p className="font-semibold">
              El desafío no es válido todavía: {problemas.length} problema{problemas.length === 1 ? "" : "s"}.
            </p>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {problemas.map((p, i) => (
                <li key={`${p.campo}-${i}`}>
                  <strong>{etiquetaCampo(p.campo)}:</strong> {p.mensaje}
                </li>
              ))}
            </ul>
          </div>
        )}
        {valido && problemas.length === 0 && (
          <p role="status" className="mt-4 rounded-xl border border-green-300 bg-green-50 p-3 text-sm text-green-900">
            ✓ El desafío pasó todas las comprobaciones: el setup corre, la solución se acepta a sí misma, los errores típicos fallan y las ayudas cumplen sus reglas.
          </p>
        )}
      </div>

      <section className="mt-4 space-y-4 rounded-xl border border-slate-200 bg-white p-4" aria-labelledby="sec-general">
        <h2 id="sec-general" className="text-lg font-semibold text-slate-900">Datos generales</h2>
        <CampoTexto etiqueta="Título" valor={b.titulo} alCambiar={(v) => cambiar({ titulo: v }, "titulo")} error={error("titulo")} maxLength={160} />
        <div className="grid gap-4 sm:grid-cols-3">
          <CampoSeleccion
            etiqueta="Concepto"
            valor={b.concepto}
            alCambiar={(v) => cambiar({ concepto: v }, "concepto")}
            error={error("concepto")}
            placeholder="Elige un concepto"
            opciones={opciones.conceptos.map((c) => ({ valor: c.codigo, etiqueta: c.nombre }))}
          />
          <CampoSeleccion
            etiqueta="Dificultad"
            valor={b.dificultad}
            alCambiar={(v) => cambiar({ dificultad: v as BorradorDesafio["dificultad"] }, "dificultad")}
            error={error("dificultad")}
            placeholder="Elige una dificultad"
            opciones={opciones.dificultades.map((d) => ({ valor: d, etiqueta: ETIQUETA_DIFICULTAD[d] }))}
          />
          <CampoTexto
            etiqueta="Tiempo de referencia (segundos)"
            type="number"
            min={1}
            max={7200}
            valor={b.tiempo_referencia_seg}
            alCambiar={(v) => cambiar({ tiempo_referencia_seg: v }, "tiempo_referencia_seg")}
            error={error("tiempo_referencia_seg")}
            ayuda={tiempoPorDefecto ? `Vacío = ${tiempoPorDefecto} s (el de ${b.dificultad} en reglas.json).` : "Vacío = el de la dificultad elegida."}
          />
        </div>
        <CampoArea etiqueta="Enunciado" valor={b.enunciado} alCambiar={(v) => cambiar({ enunciado: v }, "enunciado")} error={error("enunciado")} filas={5} maxLength={6000} />
        <CampoArea
          etiqueta="Recursos (uno por línea, opcional)"
          valor={b.recursos}
          alCambiar={(v) => cambiar({ recursos: v }, "recursos")}
          error={error("recursos")}
          filas={3}
          ayuda="Pistas conceptuales breves que el estudiante ve junto al enunciado."
        />
      </section>

      <section className="mt-4 space-y-4 rounded-xl border border-slate-200 bg-white p-4" aria-labelledby="sec-sql">
        <h2 id="sec-sql" className="text-lg font-semibold text-slate-900">Base de datos y solución</h2>
        <CampoArea
          etiqueta="Esquema (lo que ve el estudiante)"
          codigo
          valor={b.esquema_sql}
          alCambiar={(v) => cambiar({ esquema_sql: v }, "esquema_sql")}
          error={error("esquema_sql")}
          filas={6}
          ayuda="Los CREATE TABLE que se muestran al estudiante."
        />
        <CampoArea
          etiqueta="Datos de prueba (setup)"
          codigo
          valor={b.sandbox_setup_sql}
          alCambiar={(v) => cambiar({ sandbox_setup_sql: v }, "sandbox_setup_sql")}
          error={error("sandbox_setup_sql")}
          filas={8}
          ayuda="Lo ejecuta el sistema (CREATE TABLE e INSERT). No se muestra al estudiante. No se permiten ATTACH ni PRAGMA."
        />
        <CampoArea
          etiqueta="Solución de referencia"
          codigo
          valor={b.solucion_referencia}
          alCambiar={(v) => cambiar({ solucion_referencia: v }, "solucion_referencia")}
          error={error("solucion_referencia")}
          filas={4}
          ayuda="Una sola consulta SELECT (o WITH … SELECT). Si tiene ORDER BY, el orden importará al evaluar."
        />
      </section>

      <section className="mt-4 space-y-4 rounded-xl border border-slate-200 bg-white p-4" aria-labelledby="sec-errores">
        <h2 id="sec-errores" className="text-lg font-semibold text-slate-900">Errores típicos</h2>
        <p className="text-sm text-slate-600">
          Exactamente {opciones.n_errores_tipicos}. Cada ejemplo debe ser una consulta que <strong>falle</strong> (resultado distinto o error).
        </p>
        {error("errores_tipicos") && <p className="text-sm text-red-700">{error("errores_tipicos")}</p>}
        {b.errores_tipicos.map((e, i) => (
          <fieldset key={i} className="space-y-3 rounded-lg border border-slate-200 p-3">
            <legend className="px-1 text-sm font-semibold text-slate-800">Error típico {i + 1}</legend>
            <CampoTexto etiqueta="Descripción" valor={e.descripcion} alCambiar={(v) => cambiarError(i, "descripcion", v)} error={error(`errores_tipicos.${i}.descripcion`)} maxLength={500} />
            <CampoArea etiqueta="Ejemplo (consulta incorrecta)" codigo valor={e.ejemplo} alCambiar={(v) => cambiarError(i, "ejemplo", v)} error={error(`errores_tipicos.${i}.ejemplo`)} filas={3} />
          </fieldset>
        ))}
      </section>

      <section className="mt-4 space-y-4 rounded-xl border border-slate-200 bg-white p-4" aria-labelledby="sec-ayudas">
        <h2 id="sec-ayudas" className="text-lg font-semibold text-slate-900">Ayudas de respaldo</h2>
        <p className="text-sm text-slate-600">Se muestran cuando el LLM no está disponible o su respuesta no pasa los controles.</p>
        {TIPOS_AYUDA.map((t) => (
          <fieldset key={t} className="space-y-3 rounded-lg border border-slate-200 p-3">
            <legend className="px-1 text-sm font-semibold text-slate-800">{AYUDAS[t].titulo}</legend>
            <p className="text-xs text-slate-500">{AYUDAS[t].guia}</p>
            <CampoArea etiqueta="Mensaje" valor={b.ayudas_respaldo[t].mensaje} alCambiar={(v) => cambiarAyuda(t, "mensaje", v)} error={error(`ayudas_respaldo.${t}.mensaje`)} filas={3} maxLength={2000} />
            {AYUDAS[t].conCodigo && (
              <CampoArea etiqueta="Código SQL" codigo valor={b.ayudas_respaldo[t].codigo_sql} alCambiar={(v) => cambiarAyuda(t, "codigo_sql", v)} error={error(`ayudas_respaldo.${t}.codigo_sql`)} filas={4} />
            )}
            {!AYUDAS[t].conCodigo && error(`ayudas_respaldo.${t}.codigo_sql`) && <p className="text-sm text-red-700">{error(`ayudas_respaldo.${t}.codigo_sql`)}</p>}
          </fieldset>
        ))}
      </section>

      <div className="mt-4 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => void validar()}
          disabled={ocupado !== null}
          className="rounded-lg border border-indigo-300 px-4 py-2 text-sm font-semibold text-indigo-800 hover:bg-indigo-50 disabled:opacity-60"
        >
          {ocupado === "validar" ? "Validando…" : "Validar sin guardar"}
        </button>
        <button
          type="button"
          onClick={() => setVista((v) => !v)}
          aria-pressed={vista}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          {vista ? "Ocultar vista previa" : "Vista previa"}
        </button>
        <button type="submit" disabled={ocupado !== null} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-60">
          {ocupado === "guardar" ? "Validando y guardando…" : desafio ? "Guardar cambios" : "Crear desafío"}
        </button>
        <Link to="/docente/desafios" className="rounded-lg px-4 py-2 text-sm font-medium text-slate-700 underline">
          Cancelar
        </Link>
      </div>

      {vista && (
        <div className="mt-4">
          <VistaPreviaDesafio
            titulo={b.titulo.trim()}
            concepto={concepto}
            dificultad={b.dificultad}
            tiempoSeg={Number.isFinite(tiempoNum) && tiempoNum > 0 ? tiempoNum : tiempoPorDefecto ?? null}
            enunciado={b.enunciado.trim()}
            recursos={b.recursos.split("\n").map((r) => r.trim()).filter(Boolean)}
            esquema={b.esquema_sql.trim()}
          />
        </div>
      )}

      {confirmar && (
        <DialogoConfirmacion
          titulo="Este desafío ya se usó"
          mensaje={confirmar}
          etiquetaConfirmar="Guardar de todos modos"
          etiquetaCancelar="Volver al formulario"
          etiquetaOcupado="Guardando…"
          ocupado={ocupado === "guardar"}
          onConfirmar={() => {
            setConfirmar(null);
            void guardar(true);
          }}
          onCancelar={() => setConfirmar(null)}
        />
      )}
    </form>
  );
}
