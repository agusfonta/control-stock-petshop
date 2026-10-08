/** Linea de stock insuficiente devuelta por un 409 de venta (`detail.faltantes`). */
export interface Faltante {
  producto_id: string;
  solicitado: number;
  disponible: number;
}

/** Error normalizado de la API: `status 0` representa un error de red. */
export class ApiError extends Error {
  readonly status: number;
  readonly fieldErrors: Record<string, string>;
  readonly faltantes: Faltante[] | undefined;

  constructor(
    status: number,
    message: string,
    fieldErrors: Record<string, string> = {},
    faltantes?: Faltante[],
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
    this.faltantes = faltantes;
  }
}

const MENSAJE_POR_ESTADO: Record<number, string> = {
  0: "No se pudo conectar con el servidor",
  401: "Tu sesión no es válida. Volvé a iniciar sesión",
  403: "No tenés permiso para esta acción",
  404: "No se encontró lo que buscabas",
  409: "La operación entra en conflicto con el estado actual",
  422: "Revisá los datos ingresados",
  429: "Demasiados intentos. Probá de nuevo en unos minutos",
  503: "El servidor no está disponible",
};

function mensajePorEstado(status: number): string {
  const conocido = MENSAJE_POR_ESTADO[status];
  if (conocido !== undefined) return conocido;
  return status >= 500 ? "Error del servidor" : "No se pudo completar la acción";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFaltante(value: unknown): value is Faltante {
  return (
    isRecord(value) &&
    typeof value.producto_id === "string" &&
    typeof value.solicitado === "number" &&
    typeof value.disponible === "number"
  );
}

/** `["body", "lineas", 0, "cantidad"]` -> `"lineas.0.cantidad"` (sin la ubicacion inicial). */
function campoDesdeLoc(loc: unknown): string | null {
  if (!Array.isArray(loc)) return null;
  const partes = loc.slice(1).map(String);
  return partes.length > 0 ? partes.join(".") : null;
}

function erroresDeCampo(detail: unknown[]): Record<string, string> {
  const campos: Record<string, string> = {};
  for (const item of detail) {
    if (!isRecord(item) || typeof item.msg !== "string") continue;
    const campo = campoDesdeLoc(item.loc);
    if (campo !== null && !(campo in campos)) campos[campo] = item.msg;
  }
  return campos;
}

/** Construye un `ApiError` desde los tres formatos de `detail` (string, lista Pydantic, objeto). */
export function parseApiError(status: number, body: unknown): ApiError {
  const detail = isRecord(body) ? body.detail : undefined;
  if (typeof detail === "string" && detail.length > 0) {
    return new ApiError(status, detail);
  }
  if (Array.isArray(detail)) {
    return new ApiError(status, mensajePorEstado(status), erroresDeCampo(detail));
  }
  if (isRecord(detail)) {
    const mensaje = typeof detail.mensaje === "string" ? detail.mensaje : mensajePorEstado(status);
    const faltantes = Array.isArray(detail.faltantes) ? detail.faltantes.filter(isFaltante) : undefined;
    return new ApiError(status, mensaje, {}, faltantes);
  }
  return new ApiError(status, mensajePorEstado(status));
}
