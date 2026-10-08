import { Search, X } from "lucide-react";
import type { ReactElement } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/shared/lib/utils";

interface SearchFieldProps {
  value: string;
  onChange: (value: string) => void;
  /** Nombre accesible (no hay label visible). */
  label: string;
  placeholder?: string;
  className?: string;
}

/** Buscador de listados con icono y boton "Limpiar" (UX7). */
export function SearchField({ value, onChange, label, placeholder, className }: SearchFieldProps): ReactElement {
  return (
    <div className={cn("relative w-full sm:max-w-sm", className)}>
      <Search
        className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
        aria-hidden="true"
      />
      <Input
        type="search"
        role="searchbox"
        aria-label={label}
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete="off"
        className="h-10 pr-10 pl-9 [&::-webkit-search-cancel-button]:hidden"
      />
      {value !== "" && (
        <Button
          type="button"
          variant="ghost"
          size="icon"
          className="absolute top-1/2 right-1 size-8 -translate-y-1/2 text-muted-foreground"
          aria-label="Limpiar búsqueda"
          onClick={() => onChange("")}
        >
          <X aria-hidden="true" />
        </Button>
      )}
    </div>
  );
}
