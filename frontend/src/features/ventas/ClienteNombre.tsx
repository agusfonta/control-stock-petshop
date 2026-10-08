import type { ReactElement } from "react";
import { useClientePuntual, useClientesIndex } from "@/features/ventas/api";

/** Nombre del cliente de una venta: indice cacheado (D12) y, si fue dado de baja, consulta puntual; "—" si no hay. */
export function ClienteNombre({ id }: { id: string | null }): ReactElement {
  const indice = useClientesIndex();
  const enIndice = id !== null ? indice.data?.get(id) : undefined;
  const puntual = useClientePuntual(id, indice.isSuccess && enIndice === undefined);
  if (id === null) return <span className="text-muted-foreground">Sin cliente</span>;
  const nombre = enIndice?.nombre ?? puntual.data?.nombre;
  return <span>{nombre ?? "—"}</span>;
}
