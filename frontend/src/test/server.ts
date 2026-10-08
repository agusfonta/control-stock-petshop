import { setupServer } from "msw/node";

/** Servidor MSW compartido; cada test agrega sus handlers con `server.use(...)`. */
export const server = setupServer();
