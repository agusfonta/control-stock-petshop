import { afterEach, describe, expect, it } from "vitest";
import { focoDeMenu, menuAbierto, menuCerrado, dialogoAbierto, dialogoCerrado, VENTANA_MS } from "@/shared/lib/focoMenu";

function boton(): HTMLButtonElement {
  const b = document.createElement("button");
  document.body.appendChild(b);
  return b;
}

afterEach(() => {
  document.body.innerHTML = "";
  // Deja el modulo en estado neutro para el test siguiente.
  menuAbierto(null);
  dialogoAbierto(Number.MAX_SAFE_INTEGER);
});

describe("foco al cerrar un dialogo abierto desde un menu", () => {
  it("devuelve el foco al boton del menu cuando el dialogo abre justo despues de cerrarse el menu", () => {
    const trigger = boton();
    menuAbierto(trigger);
    menuCerrado(1000);
    dialogoAbierto(1000 + 50);
    const evento = new Event("focus", { cancelable: true });
    dialogoCerrado(evento);
    expect(evento.defaultPrevented).toBe(true);
    expect(trigger).toHaveFocus();
  });

  it("no hace nada si el dialogo no viene de un menu (abre mucho despues)", () => {
    const trigger = boton();
    menuAbierto(trigger);
    menuCerrado(1000);
    dialogoAbierto(1000 + VENTANA_MS + 1);
    const evento = new Event("focus", { cancelable: true });
    dialogoCerrado(evento);
    expect(evento.defaultPrevented).toBe(false);
    expect(trigger).not.toHaveFocus();
  });

  it("no restaura dos veces ni un boton que ya no esta en el documento", () => {
    const trigger = boton();
    menuAbierto(trigger);
    menuCerrado(1000);
    dialogoAbierto(1010);
    trigger.remove();
    const evento = new Event("focus", { cancelable: true });
    dialogoCerrado(evento);
    expect(evento.defaultPrevented).toBe(false);

    const otro = boton();
    menuAbierto(otro);
    menuCerrado(2000);
    dialogoAbierto(2010);
    dialogoCerrado(new Event("focus", { cancelable: true }));
    const segundo = new Event("focus", { cancelable: true });
    dialogoCerrado(segundo);
    expect(segundo.defaultPrevented).toBe(false);
  });
});

describe("focoDeMenu", () => {
  it("encadena los handlers propios del dialogo con el de restauracion", () => {
    const llamados: string[] = [];
    const { onCloseAutoFocus, onOpenAutoFocus } = focoDeMenu({
      onOpenAutoFocus: () => llamados.push("abrir"),
      onCloseAutoFocus: () => llamados.push("cerrar"),
    });
    onOpenAutoFocus(new Event("focus", { cancelable: true }));
    onCloseAutoFocus(new Event("focus", { cancelable: true }));
    expect(llamados).toEqual(["abrir", "cerrar"]);
  });

  it("respeta el preventDefault de un handler propio y no pisa el foco", () => {
    const trigger = boton();
    menuAbierto(trigger);
    menuCerrado(Date.now());
    const { onCloseAutoFocus, onOpenAutoFocus } = focoDeMenu({ onCloseAutoFocus: (e: Event) => e.preventDefault() });
    onOpenAutoFocus(new Event("focus", { cancelable: true }));
    onCloseAutoFocus(new Event("focus", { cancelable: true }));
    expect(trigger).not.toHaveFocus();
  });
});
