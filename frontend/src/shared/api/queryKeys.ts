/** Fabrica de claves de React Query por recurso (D6). Las invalidaciones usan los prefijos `all`. */
type Params = Record<string, unknown>;

export const queryKeys = {
  productos: {
    all: ["productos"] as const,
    list: (params: Params) => ["productos", "list", params] as const,
    buscar: (q: string, params?: Params) => ["productos", "buscar", q, params ?? {}] as const,
    detail: (id: string) => ["productos", "detail", id] as const,
  },
  stock: {
    all: ["stock"] as const,
    list: (params: Params) => ["stock", "list", params] as const,
    alertas: ["stock", "alertas"] as const,
  },
  clientes: {
    all: ["clientes"] as const,
    list: (params: Params) => ["clientes", "list", params] as const,
    buscar: (q: string) => ["clientes", "buscar", q] as const,
    detail: (id: string) => ["clientes", "detail", id] as const,
    historial: (id: string, params?: Params) => ["clientes", "historial", id, params ?? {}] as const,
  },
  distribuidoras: {
    all: ["distribuidoras"] as const,
    list: (params: Params) => ["distribuidoras", "list", params] as const,
    detail: (id: string) => ["distribuidoras", "detail", id] as const,
    precios: (id: string) => ["distribuidoras", "precios", id] as const,
    comparar: (productoId: string) => ["distribuidoras", "comparar", productoId] as const,
    cuenta: (id: string) => ["distribuidoras", "cuenta", id] as const,
  },
  pedidos: {
    all: ["pedidos"] as const,
    list: (params: Params) => ["pedidos", "list", params] as const,
    detail: (id: string) => ["pedidos", "detail", id] as const,
  },
  pagos: {
    all: ["pagos"] as const,
    list: (params: Params) => ["pagos", "list", params] as const,
  },
  ventas: {
    all: ["ventas"] as const,
    list: (params: Params) => ["ventas", "list", params] as const,
    detail: (id: string) => ["ventas", "detail", id] as const,
  },
  reportes: {
    all: ["reportes"] as const,
    ventasDia: (fecha: string | undefined) => ["reportes", "ventas-dia", fecha ?? "hoy"] as const,
    reposicion: (params: Params) => ["reportes", "reposicion", params] as const,
    masVendidos: (params: Params) => ["reportes", "mas-vendidos", params] as const,
    margenes: (params: Params) => ["reportes", "margenes", params] as const,
  },
  indices: {
    productos: ["indices", "productos"] as const,
    distribuidoras: ["indices", "distribuidoras"] as const,
    clientes: ["indices", "clientes"] as const,
  },
} as const;
