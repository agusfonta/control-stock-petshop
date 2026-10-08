import { useEffect, useState } from "react";

/** Devuelve `value` recien despues de `delay` ms sin cambios (busqueda al tipear, decision #6). */
export function useDebouncedValue<T>(value: T, delay = 250): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(value), delay);
    return () => window.clearTimeout(id);
  }, [value, delay]);
  return debounced;
}
