import { toast } from "sonner";

/** Exito breve (UX10): no bloquea ni tapa el carrito (el Toaster va arriba al centro). */
export function notifySuccess(message: string): void {
  toast.success(message, { duration: 3000 });
}

/** Errores persistentes hasta que la persona los cierra. */
export function notifyError(message: string): void {
  toast.error(message, { duration: Infinity, closeButton: true });
}

export function notifyInfo(message: string): void {
  toast.info(message, { duration: 4000 });
}
