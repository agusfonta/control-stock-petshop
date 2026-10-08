import { type RefObject, useEffect } from "react";

interface PosShortcuts {
  inputRef: RefObject<HTMLInputElement | null>;
  onCobrar: () => void;
  /** `+` / `-` sobre la linea seleccionada; devuelve `false` si no hay linea (el caracter va al buscador). */
  onAjustarCantidad: (delta: 1 | -1) => boolean;
}

function esCampoEditable(el: Element | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  return el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName);
}

function hayDialogAbierto(): boolean {
  return document.querySelector('[role="dialog"][data-state="open"], [role="alertdialog"][data-state="open"]') !== null;
}

/**
 * Atajos globales del POS (D10, UX3): F2 o `/` buscador, F9 o Ctrl+Enter cobrar, `+`/`-` cantidad
 * y cualquier tecla imprimible con el foco suelto va al buscador conservando el caracter
 * (el lector de barras escribe como teclado).
 */
export function usePosShortcuts({ inputRef, onCobrar, onAjustarCantidad }: PosShortcuts): void {
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent): void {
      if (e.defaultPrevented || hayDialogAbierto()) return;
      const input = inputRef.current;

      if (e.key === "F2") {
        e.preventDefault();
        input?.focus();
        input?.select();
        return;
      }
      if (e.key === "F9" || (e.key === "Enter" && e.ctrlKey)) {
        e.preventDefault();
        onCobrar();
        return;
      }

      const activo = document.activeElement;
      if (esCampoEditable(activo) || e.ctrlKey || e.metaKey || e.altKey || e.key.length !== 1) return;
      const sobreBotonOEnlace = activo instanceof HTMLElement && ["BUTTON", "A"].includes(activo.tagName);
      if (sobreBotonOEnlace && e.key === " ") return; // Espacio activa el boton enfocado.

      if (e.key === "/") {
        e.preventDefault();
        input?.focus();
        input?.select();
        return;
      }
      if ((e.key === "+" || e.key === "-") && onAjustarCantidad(e.key === "+" ? 1 : -1)) {
        e.preventDefault();
        return;
      }
      // Sin preventDefault: el navegador escribe el caracter en el campo recien enfocado.
      input?.focus();
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [inputRef, onCobrar, onAjustarCantidad]);
}
