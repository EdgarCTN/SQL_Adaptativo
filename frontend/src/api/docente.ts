import { cliente } from "./cliente";
import type {
  BorradorDesafio,
  CuerpoDesafio,
  DesafioDocente,
  FiltrosDocente,
  ListaDocente,
  OpcionesDocente,
  TipoAyuda,
  Validacion,
} from "./tiposDocente";
import { TIPOS_AYUDA } from "./tiposDocente";

const BASE = "/docente/desafios";

export const opcionesDocente = () => cliente.get<OpcionesDocente>(`${BASE}/opciones`).then((r) => r.data);

export const listarDesafiosDocente = (f: FiltrosDocente) => {
  const params = Object.fromEntries(Object.entries(f).filter(([, v]) => v));
  return cliente.get<ListaDocente>(BASE, { params }).then((r) => r.data);
};

export const obtenerDesafioDocente = (id: number) => cliente.get<DesafioDocente>(`${BASE}/${id}`).then((r) => r.data);

export const validarDesafio = (cuerpo: CuerpoDesafio, desafioId?: number) =>
  cliente.post<Validacion>(`${BASE}/validar`, cuerpo, { params: desafioId ? { desafio_id: desafioId } : undefined }).then((r) => r.data);

export const crearDesafio = (cuerpo: CuerpoDesafio) => cliente.post<DesafioDocente>(BASE, cuerpo).then((r) => r.data);

/** Si el desafío ya tiene sesiones y cambia la solución o el setup, el servidor responde 409 hasta recibir `confirmar`. */
export const actualizarDesafio = (id: number, cuerpo: CuerpoDesafio, confirmar = false) =>
  cliente.put<DesafioDocente>(`${BASE}/${id}`, { ...cuerpo, confirmar_cambio: confirmar }).then((r) => r.data);

export const activarDesafio = (id: number) => cliente.post<{ mensaje: string }>(`${BASE}/${id}/activar`).then((r) => r.data);
export const desactivarDesafio = (id: number) => cliente.post<{ mensaje: string }>(`${BASE}/${id}/desactivar`).then((r) => r.data);
export const eliminarDesafio = (id: number) => cliente.delete<{ mensaje: string }>(`${BASE}/${id}`).then((r) => r.data);

// ---------- Formulario <-> API ----------
export function borradorVacio(nErrores = 3): BorradorDesafio {
  return {
    titulo: "",
    enunciado: "",
    recursos: "",
    concepto: "",
    dificultad: "",
    esquema_sql: "",
    sandbox_setup_sql: "",
    solucion_referencia: "",
    errores_tipicos: Array.from({ length: nErrores }, () => ({ descripcion: "", ejemplo: "" })),
    ayudas_respaldo: { AY1: { mensaje: "", codigo_sql: "" }, AY2: { mensaje: "", codigo_sql: "" }, AY3: { mensaje: "", codigo_sql: "" }, AY4: { mensaje: "", codigo_sql: "" } },
    tiempo_referencia_seg: "",
  };
}

export function borradorDe(d: DesafioDocente, nErrores = 3): BorradorDesafio {
  const errores = d.errores_tipicos.map((e) => ({ ...e }));
  while (errores.length < nErrores) errores.push({ descripcion: "", ejemplo: "" });
  const ayudas = borradorVacio(nErrores).ayudas_respaldo;
  for (const t of TIPOS_AYUDA) {
    const a = d.ayudas_respaldo[t];
    if (a) ayudas[t] = { mensaje: a.mensaje, codigo_sql: a.codigo_sql ?? "" };
  }
  return {
    titulo: d.titulo,
    enunciado: d.enunciado,
    recursos: d.recursos.join("\n"),
    concepto: d.concepto.codigo,
    dificultad: d.dificultad,
    esquema_sql: d.esquema_sql,
    sandbox_setup_sql: d.sandbox_setup_sql,
    solucion_referencia: d.solucion_referencia,
    errores_tipicos: errores,
    ayudas_respaldo: ayudas,
    tiempo_referencia_seg: String(d.tiempo_referencia_seg),
  };
}

export function cuerpoDe(b: BorradorDesafio): CuerpoDesafio {
  const ayudas = {} as CuerpoDesafio["ayudas_respaldo"];
  for (const t of TIPOS_AYUDA as TipoAyuda[]) {
    ayudas[t] = { mensaje: b.ayudas_respaldo[t].mensaje, codigo_sql: b.ayudas_respaldo[t].codigo_sql.trim() || null };
  }
  const tiempo = Number.parseInt(b.tiempo_referencia_seg, 10);
  return {
    titulo: b.titulo,
    enunciado: b.enunciado,
    recursos: b.recursos.split("\n").map((r) => r.trim()).filter(Boolean),
    concepto: b.concepto,
    dificultad: b.dificultad,
    esquema_sql: b.esquema_sql,
    sandbox_setup_sql: b.sandbox_setup_sql,
    solucion_referencia: b.solucion_referencia,
    errores_tipicos: b.errores_tipicos,
    ayudas_respaldo: ayudas,
    tiempo_referencia_seg: Number.isFinite(tiempo) && tiempo > 0 ? tiempo : null,
  };
}
