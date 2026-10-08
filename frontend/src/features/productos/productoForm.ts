import { z } from "zod";
import { fraccionAMargenPct, margenPctAFraccion, parseMargenPct } from "@/features/productos/pricing";
import type { Producto, ProductoCreate, Unidad } from "@/shared/api/types";
import { centsToApi, toCents } from "@/shared/lib/money";

export const UNIDADES: readonly { value: Unidad; label: string }[] = [
  { value: "unidad", label: "Unidad" },
  { value: "bolsa", label: "Bolsa" },
  { value: "caja", label: "Caja" },
];

export const SIN_DISTRIBUIDORA = "none";

const SKU = /^[A-Za-z0-9][A-Za-z0-9_-]*$/;
const MONTO = /^\d+(\.\d{1,2})?$/;
const ENTERO = /^\d+$/;

/** Interpreta un importe tipeado ("18000", "18000,50") como centavos; `null` si es invalido o <= 0. */
export function parseMontoCents(texto: string): number | null {
  const limpio = texto.trim().replace(",", ".");
  if (!MONTO.test(limpio)) return null;
  const cents = toCents(limpio);
  return cents > 0 ? cents : null;
}

const opcional = (max: number) => z.string().trim().max(max, `Máximo ${max} caracteres`);

export const productoSchema = z.object({
  sku: z
    .string()
    .trim()
    .min(1, "Ingresá el SKU")
    .max(50, "Máximo 50 caracteres")
    .regex(SKU, "Usá letras, números, guiones o guion bajo"),
  nombre: z.string().trim().min(1, "Ingresá el nombre").max(200, "Máximo 200 caracteres"),
  marca: opcional(100),
  categoria: opcional(100),
  unidad: z.enum(["unidad", "bolsa", "caja"]),
  costo: z.string().refine((v) => parseMontoCents(v) !== null, "Ingresá un costo mayor a 0 (ej. 18000 o 18000,50)"),
  margen: z.string().refine((v) => parseMargenPct(v) !== null, "Ingresá el margen en % (ej. 35)"),
  stockInicial: z.string().refine((v) => v.trim() === "" || ENTERO.test(v.trim()), "Ingresá un número entero"),
  stockMinimo: z.string().refine((v) => ENTERO.test(v.trim()), "Ingresá un número entero (0 o más)"),
  distribuidoraId: z.string(),
});

export type ProductoFormValues = z.infer<typeof productoSchema>;

export function valoresVacios(): ProductoFormValues {
  return {
    sku: "",
    nombre: "",
    marca: "",
    categoria: "",
    unidad: "unidad",
    costo: "",
    margen: "",
    stockInicial: "0",
    stockMinimo: "0",
    distribuidoraId: SIN_DISTRIBUIDORA,
  };
}

/** Valores del formulario de edicion a partir del producto (margen fraccion -> %). */
export function valoresDesdeProducto(p: Producto): ProductoFormValues {
  return {
    sku: p.sku,
    nombre: p.nombre,
    marca: p.marca ?? "",
    categoria: p.categoria ?? "",
    unidad: p.unidad,
    costo: String(toCents(p.costo) / 100),
    margen: String(fraccionAMargenPct(p.margen_pct)),
    stockInicial: "0",
    stockMinimo: String(p.stock_minimo),
    distribuidoraId: p.distribuidora_default_id ?? SIN_DISTRIBUIDORA,
  };
}

/** Cuerpo comun de alta y edicion: montos como string, margen como fraccion (decision #9). */
export function aPayload(v: ProductoFormValues): Omit<ProductoCreate, "stock_actual"> {
  const costo = parseMontoCents(v.costo);
  const margen = parseMargenPct(v.margen);
  if (costo === null || margen === null) throw new Error("Formulario de producto invalido");
  return {
    sku: v.sku.trim(),
    nombre: v.nombre.trim(),
    marca: v.marca.trim() === "" ? null : v.marca.trim(),
    categoria: v.categoria.trim() === "" ? null : v.categoria.trim(),
    unidad: v.unidad,
    costo: centsToApi(costo),
    margen_pct: margenPctAFraccion(margen),
    stock_minimo: Number(v.stockMinimo.trim()),
    distribuidora_default_id: v.distribuidoraId === SIN_DISTRIBUIDORA ? null : v.distribuidoraId,
  };
}

/** Alta: suma el stock inicial (solo existe al crear). */
export function aPayloadAlta(v: ProductoFormValues): ProductoCreate {
  return { ...aPayload(v), stock_actual: v.stockInicial.trim() === "" ? 0 : Number(v.stockInicial.trim()) };
}
