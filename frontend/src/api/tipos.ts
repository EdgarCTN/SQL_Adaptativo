export type Rol = "estudiante" | "docente" | "administrador";

export interface Usuario {
  id: number;
  nombre: string;
  correo: string;
  rol: Rol;
  activo: boolean;
  creado_en: string;
  linea_base_completada: boolean;
}

export interface TokenOut {
  access_token: string;
  token_type: string;
  expira_en: number;
  usuario: Usuario;
}

export interface Mensaje {
  ok: boolean;
  mensaje: string;
}
