import type { Usuario } from "../api/tipos";

/** Siguiente paso tras terminar el diagnóstico. Provisional: la entrega 6 lo cambia a /desafios. */
export const DESTINO_TRAS_DIAGNOSTICO = "/perfil";

/** Destino tras iniciar sesión: el estudiante sin diagnóstico empieza por el consentimiento. */
export function destinoTrasLogin(usuario: Usuario): string {
  if (usuario.rol === "estudiante" && !usuario.linea_base_completada) return "/consentimiento";
  return DESTINO_TRAS_DIAGNOSTICO;
}
