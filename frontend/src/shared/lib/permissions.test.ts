import { renderHook } from "@testing-library/react";
import { act } from "react";
import { beforeEach, describe, expect, it } from "vitest";
import { useSession } from "@/features/auth/session";
import { PERMISOS, can, type Permiso, useCan } from "@/shared/lib/permissions";
import type { Me, Rol } from "@/shared/api/types";

/** Matriz RBAC del spec `auth-rbac` + endpoints del backend: duena-only vs ambos roles. */
const SOLO_DUENA: Permiso[] = [
  "productos.editar",
  "stock.ajustar",
  "ventas.anular",
  "clientes.editar",
  "distribuidoras.editar",
  "compras.cancelar",
  "compras.pagos",
  "reportes.completos",
];

const usuario = (rol: Rol): Me => ({ id: "u", email: `${rol}@petshop.local`, rol, activo: true });

beforeEach(() => {
  useSession.setState({ status: "loading", accessToken: null, user: null, expired: false });
});

describe("PERMISOS (matriz RBAC)", () => {
  it("define exactamente los permisos esperados", () => {
    expect(Object.keys(PERMISOS).sort()).toEqual([...SOLO_DUENA].sort());
  });

  it.each(SOLO_DUENA)("%s es exclusivo de la duena", (permiso) => {
    expect(PERMISOS[permiso]).toEqual(["duena"]);
    expect(can("duena", permiso)).toBe(true);
    expect(can("mostrador", permiso)).toBe(false);
  });

  it("sin rol (anonimo) no se tiene ningun permiso", () => {
    for (const permiso of SOLO_DUENA) expect(can(null, permiso)).toBe(false);
  });
});

describe("useCan", () => {
  it("lee el rol del store de sesion y reacciona a sus cambios", () => {
    const { result } = renderHook(() => useCan("ventas.anular"));
    expect(result.current).toBe(false);

    act(() => useSession.setState({ status: "authenticated", user: usuario("mostrador") }));
    expect(result.current).toBe(false);

    act(() => useSession.setState({ status: "authenticated", user: usuario("duena") }));
    expect(result.current).toBe(true);

    act(() => useSession.setState({ status: "anonymous", user: null }));
    expect(result.current).toBe(false);
  });
});
