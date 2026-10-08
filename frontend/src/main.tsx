import "@fontsource-variable/figtree";
import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router";
import { AppRoutes } from "@/app/router";
import { Toaster } from "@/components/ui/sonner";
import "@/index.css";
import { queryClient } from "@/shared/api/queryClient";

const rootElement = document.getElementById("root");
if (rootElement === null) {
  throw new Error("Missing #root element");
}

createRoot(rootElement).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
      {/* Arriba al centro: no tapa el carrito ni el boton Cobrar (UX10). */}
      <Toaster position="top-center" />
    </QueryClientProvider>
  </StrictMode>,
);
