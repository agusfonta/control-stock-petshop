import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";
import { type ResultadoCobro, cobrarVenta } from "@/features/pos/checkout";
import type { PagoDraft } from "@/features/pos/payments";
import { queryKeys } from "@/shared/api/queryKeys";

interface UseCheckout {
  enviando: boolean;
  /** `null` si ya hay un envio en curso (evita doble envio). */
  cobrar: (pagos: readonly PagoDraft[], opciones?: { reintento?: boolean }) => Promise<ResultadoCobro | null>;
}

/** Ejecuta el cobro (D9) y refresca lo que cambia al vender: stock, alertas, productos, ventas, reportes, clientes (D6). */
export function useCheckout(): UseCheckout {
  const queryClient = useQueryClient();
  const [enviando, setEnviando] = useState(false);
  const enCurso = useRef(false);

  const cobrar = useCallback<UseCheckout["cobrar"]>(
    async (pagos, opciones) => {
      if (enCurso.current) return null;
      enCurso.current = true;
      setEnviando(true);
      try {
        const resultado = await cobrarVenta(pagos, opciones);
        if (resultado.tipo === "ok") {
          for (const key of [
            queryKeys.stock.all,
            queryKeys.productos.all,
            queryKeys.ventas.all,
            queryKeys.reportes.all,
            queryKeys.clientes.all,
          ]) {
            void queryClient.invalidateQueries({ queryKey: key });
          }
        } else if (resultado.tipo === "faltantes" || (resultado.tipo === "error" && resultado.refrescar)) {
          void queryClient.invalidateQueries({ queryKey: queryKeys.productos.all });
          void queryClient.invalidateQueries({ queryKey: queryKeys.clientes.all });
        }
        return resultado;
      } finally {
        enCurso.current = false;
        setEnviando(false);
      }
    },
    [queryClient],
  );

  return { enviando, cobrar };
}
