export type Errores = Record<string, string>;

const REGEX_CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function validarNombre(v: string): string | null {
  const n = v.trim();
  if (!n) return "Escribe tu nombre.";
  if (n.length < 2) return "El nombre debe tener al menos 2 caracteres.";
  if (n.length > 120) return "El nombre no puede superar los 120 caracteres.";
  return null;
}

export function validarCorreo(v: string): string | null {
  const c = v.trim();
  if (!c) return "Escribe tu correo.";
  if (!REGEX_CORREO.test(c)) return "Escribe un correo válido, por ejemplo nombre@universidad.edu.";
  return null;
}

export function validarContrasenaNueva(v: string): string | null {
  if (!v) return "Escribe una contraseña.";
  if (v.length < 8) return "La contraseña debe tener al menos 8 caracteres.";
  if (v.length > 128) return "La contraseña no puede superar los 128 caracteres.";
  if (!/[A-Za-z\u00C0-\u024F]/.test(v) || !/\d/.test(v)) return "Debe incluir al menos una letra y un número.";
  return null;
}

export function validarObligatorio(v: string, mensaje: string): string | null {
  return v ? null : mensaje;
}

/** Quita las entradas sin error y devuelve solo los mensajes. */
export function juntarErrores(candidatos: Record<string, string | null>): Errores {
  const salida: Errores = {};
  for (const [campo, mensaje] of Object.entries(candidatos)) if (mensaje) salida[campo] = mensaje;
  return salida;
}
