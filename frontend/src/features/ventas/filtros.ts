/** Filtros de fecha del listado de ventas: `YYYY-MM-DD` local -> intervalo [inicio, inicio del dia siguiente) (decision #8). */

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/** Fecha local del navegador como `YYYY-MM-DD`. */
export function hoyLocal(ahora: Date = new Date()): string {
  return `${ahora.getFullYear()}-${pad(ahora.getMonth() + 1)}-${pad(ahora.getDate())}`;
}

function inicioDelDia(iso: string, diasExtra = 0): string {
  const [y = 0, m = 1, d = 1] = iso.split("-").map(Number);
  return new Date(y, m - 1, d + diasExtra).toISOString();
}

/** Parametros `desde`/`hasta` de `GET /api/ventas`; ambos bordes del rango son inclusivos para la persona. */
export function rangoQuery(desde: string, hasta: string): { desde: string | undefined; hasta: string | undefined } {
  return {
    desde: desde === "" ? undefined : inicioDelDia(desde),
    hasta: hasta === "" ? undefined : inicioDelDia(hasta, 1),
  };
}

export function validarRango(desde: string, hasta: string): string | null {
  if (desde !== "" && hasta !== "" && desde > hasta) return "La fecha “Desde” no puede ser posterior a “Hasta”.";
  return null;
}
