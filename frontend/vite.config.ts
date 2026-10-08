import path from "node:path";
import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";
import { defineConfig } from "vitest/config";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const proxyTarget = env.VITE_PROXY_TARGET ?? "http://localhost:8000";
  const usePolling = env.VITE_USE_POLLING === "true";

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    build: {
      rolldownOptions: {
        output: {
          // Separa librerias de la app para no superar el limite de 500 kB por archivo (y cachear mejor entre deploys).
          codeSplitting: {
            groups: [
              { name: "vendor-react", test: /node_modules[\/](react|react-dom|react-router|scheduler|zustand|@tanstack)[\/]/ },
              { name: "vendor-ui", test: /node_modules[\/](radix-ui|@radix-ui|lucide-react|cmdk|vaul|sonner|react-hook-form|zod|@hookform)[\/]/ },
              { name: "vendor", test: /node_modules/ },
            ],
          },
        },
      },
    },
    server: {
      watch: usePolling ? { usePolling: true, interval: 300 } : undefined,
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: "src/test/setup.ts",
      globals: true,
      css: false,
      restoreMocks: true,
      // Los tests de formularios (userEvent + Radix) superan 5 s cuando varios workers compiten.
      testTimeout: 20_000,
    },
  };
});
