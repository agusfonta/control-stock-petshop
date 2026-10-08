import { ApiError } from "@/shared/api/errors";

export type LoginField = "email" | "password";

export interface LoginFailure {
  /** Mensaje general para el Alert del formulario (sin indicar si fallo el email o la clave). */
  message: string | null;
  /** Errores del servidor para marcar campos concretos (422). */
  fields: Partial<Record<LoginField, string>>;
}

const CAMPOS: readonly LoginField[] = ["email", "password"];

/** Traduce el error de `POST /auth/login` al mensaje de la pantalla (spec: Inicio de sesion). */
export function describeLoginError(error: unknown): LoginFailure {
  if (!(error instanceof ApiError)) {
    return { message: "No pudimos iniciar sesión. Probá de nuevo.", fields: {} };
  }
  if (error.status === 401) return { message: "Email o contraseña incorrectos", fields: {} };
  if (error.status === 429) {
    return { message: "Hubo demasiados intentos. Probá de nuevo en unos minutos.", fields: {} };
  }
  if (error.status === 0 || error.status === 503) {
    return { message: "El servidor no está disponible. Probá de nuevo en un momento.", fields: {} };
  }
  if (error.status === 422) {
    const fields: Partial<Record<LoginField, string>> = {};
    for (const campo of CAMPOS) {
      const mensaje = error.fieldErrors[campo];
      if (mensaje !== undefined) fields[campo] = mensaje;
    }
    return { message: Object.keys(fields).length > 0 ? null : error.message, fields };
  }
  return { message: "No pudimos iniciar sesión. Probá de nuevo.", fields: {} };
}

/** Solo rutas internas: evita redirecciones abiertas (`//host`, `/\host`, URLs absolutas) y el bucle a /login. */
export function safeNext(next: string | null): string {
  if (next === null || !next.startsWith("/") || next.startsWith("//") || next.startsWith("/\\")) return "/pos";
  if (next === "/login" || next.startsWith("/login?") || next.startsWith("/login/")) return "/pos";
  return next;
}
