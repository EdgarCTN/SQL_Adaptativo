import type { Usuario } from "../api/tipos";

/** Siguiente paso tras terminar (o posponer) el diagnóstico: el listado de desafíos. */
export const DESTINO_TRAS_DIAGNOSTICO = "/desafios";

/** Destino tras iniciar sesión. Docentes y administradores aún no tienen pantallas propias: van al perfil. */
export function destinoTrasLogin(usuario: Usuario): string {
  if (usuario.rol !== "estudiante") return "/perfil";
  return usuario.linea_base_completada ? DESTINO_TRAS_DIAGNOSTICO : "/consentimiento";
}
