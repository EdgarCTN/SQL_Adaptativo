import { cliente } from "./cliente";
import type { CambioUsuario, FiltrosUsuarios, ListaUsuarios } from "./tiposAdmin";
import type { Rol } from "./tipos";

const BASE = "/admin/usuarios";

export const listarUsuarios = (f: FiltrosUsuarios) =>
  cliente
    .get<ListaUsuarios>(BASE, { params: { q: f.q || undefined, rol: f.rol || undefined, pagina: f.pagina, tam: f.tam } })
    .then((r) => r.data);

export const cambiarRolUsuario = (id: number, rol: Rol) =>
  cliente.put<CambioUsuario>(`${BASE}/${id}/rol`, { rol }).then((r) => r.data);

export const activarUsuario = (id: number) => cliente.post<CambioUsuario>(`${BASE}/${id}/activar`).then((r) => r.data);

export const desactivarUsuario = (id: number) => cliente.post<CambioUsuario>(`${BASE}/${id}/desactivar`).then((r) => r.data);
