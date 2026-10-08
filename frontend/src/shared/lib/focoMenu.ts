/**
 * Foco al cerrar un dialogo que se abrio desde un menu de acciones (UX12).
 *
 * El item del menu desaparece al elegirlo, asi que Radix no tiene a donde devolver el foco cuando el dialogo se
 * cierra y lo deja en <body> (el teclado "se pierde" y hay que tabular desde el principio). Recordamos el boton que
 * abrio el menu y, si un dialogo abre apenas se cierra el menu, le devolvemos el foco al cerrarlo.
 */

/** Un dialogo que abre dentro de esta ventana despues de cerrarse un menu se considera abierto desde ese menu. */
export const VENTANA_MS = 400;

type Handler = (event: Event) => void;

let disparador: HTMLElement | null = null;
let cerradoEn: number | null = null;
let origen: HTMLElement | null = null;

/** Un menu se abrio: `el` es el boton que lo abrio (el elemento con foco). */
export function menuAbierto(el: HTMLElement | null): void {
  disparador = el;
  cerradoEn = null;
}

export function menuCerrado(ahora: number = Date.now()): void {
  cerradoEn = ahora;
}

/** Un dialogo abrio: decide si viene de un menu que acaba de cerrarse. */
export function dialogoAbierto(ahora: number = Date.now()): void {
  const vieneDeMenu = disparador !== null && cerradoEn !== null && ahora - cerradoEn <= VENTANA_MS;
  origen = vieneDeMenu ? disparador : null;
  disparador = null;
  cerradoEn = null;
}

/** El dialogo termino de cerrarse: devuelve el foco al boton del menu, una sola vez. */
export function dialogoCerrado(event: Event): void {
  const destino = origen;
  origen = null;
  if (destino === null || !destino.isConnected) return;
  event.preventDefault();
  destino.focus();
}

interface HandlersFoco {
  onOpenAutoFocus?: Handler;
  onCloseAutoFocus?: Handler;
}

/** Para `*Content` de shadcn: conserva los handlers del llamador y suma la restauracion de foco. */
export function focoDeMenu(props: HandlersFoco): { onOpenAutoFocus: Handler; onCloseAutoFocus: Handler } {
  return {
    onOpenAutoFocus: (event) => {
      dialogoAbierto();
      props.onOpenAutoFocus?.(event);
    },
    onCloseAutoFocus: (event) => {
      props.onCloseAutoFocus?.(event);
      if (!event.defaultPrevented) dialogoCerrado(event);
    },
  };
}
