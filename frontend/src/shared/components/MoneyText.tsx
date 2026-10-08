import type { ReactElement } from "react";
import { type Money, formatARS, toCents } from "@/shared/lib/money";
import { cn } from "@/shared/lib/utils";

interface MoneyTextProps {
  value: Money;
  className?: string;
}

/** Importe en pesos argentinos con numeros tabulares: "$ 24.999,50". */
export function MoneyText({ value, className }: MoneyTextProps): ReactElement {
  return <span className={cn("tabular whitespace-nowrap tabular-nums", className)}>{formatARS(toCents(value))}</span>;
}
