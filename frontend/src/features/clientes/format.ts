const FECHA_HORA = new Intl.DateTimeFormat("es-AR", { dateStyle: "short", timeStyle: "short" });

/** Fecha y hora locales del navegador en formato es-AR (decision #8); "—" si no hay fecha. */
export function formatFechaHora(iso: string | null): string {
  if (iso === null) return "—";
  const fecha = new Date(iso);
  return Number.isNaN(fecha.getTime()) ? "—" : FECHA_HORA.format(fecha);
}
