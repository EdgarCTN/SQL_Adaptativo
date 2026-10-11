import type { Usuario } from "../api/tipos";

/** Destino tras iniciar sesión. Provisional: las entregas 4 y 6 lo cambian. */
export function destinoTrasLogin(_usuario: Usuario): string {
  return "/perfil";
}
