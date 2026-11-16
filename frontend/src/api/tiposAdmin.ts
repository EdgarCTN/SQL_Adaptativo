import type { Rol } from "./tipos";

/** Fila de «Usuarios»: solo la ve el administrador. Nunca incluye la contraseña. */
export interface UsuarioAdmin {
  id: number;
  nombre: string;
  correo: string;
  rol: Rol;
  activo: boolean;
  creado_en: string;
}

export interface ListaUsuarios {
  total: number;
  pagina: number;
  tam: number;
  paginas: number;
  usuarios: UsuarioAdmin[];
}

export interface CambioUsuario {
  ok: boolean;
  mensaje: string;
  usuario: UsuarioAdmin;
}

export interface FiltrosUsuarios {
  q?: string;
  rol?: Rol | "";
  pagina?: number;
  tam?: number;
}
