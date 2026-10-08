import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "@/test/server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));

afterEach(() => {
  cleanup();
  server.resetHandlers();
  try {
    window.localStorage.clear();
  } catch {
    // localStorage no disponible: nada que limpiar.
  }
});

afterAll(() => server.close());

// jsdom no implementa estas APIs que usan los componentes de shadcn/Radix.
if (typeof window.matchMedia !== "function") {
  window.matchMedia = (query: string): MediaQueryList => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
    addListener: () => undefined,
    removeListener: () => undefined,
    dispatchEvent: () => false,
  });
}

class ResizeObserverStub implements ResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
if (typeof window.ResizeObserver === "undefined") {
  window.ResizeObserver = ResizeObserverStub;
}

Element.prototype.scrollIntoView ??= () => undefined;
Element.prototype.hasPointerCapture ??= () => false;
Element.prototype.setPointerCapture ??= () => undefined;
Element.prototype.releasePointerCapture ??= () => undefined;
