import { Info } from "lucide-react";
import type { ReactElement } from "react";
import { Navigate, useSearchParams } from "react-router";
import { BootScreen } from "@/app/guards/BootScreen";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { LoginForm } from "@/features/auth/LoginForm";
import { safeNext } from "@/features/auth/loginErrors";
import { useSession } from "@/features/auth/session";
import { STORE_NAME } from "@/shared/lib/store";

/** Panel de marca (solo desktop): logo sobre `blush` + mensaje (UX9). */
function BrandPanel(): ReactElement {
  return (
    <aside className="relative hidden flex-col items-center justify-center gap-8 bg-blush p-12 lg:flex">
      <img
        src="/logo.png"
        alt={`Logo de ${STORE_NAME}`}
        width={832}
        height={787}
        className="w-full max-w-sm"
      />
      <div className="max-w-sm space-y-2 text-center">
        <p className="text-xl font-semibold tracking-tight">Tu mostrador, ordenado.</p>
        <p className="text-sm text-muted-foreground">
          Ventas, stock, clientes y reposición en un solo lugar, listos para usar desde la tablet.
        </p>
      </div>
    </aside>
  );
}

export function LoginPage(): ReactElement {
  const status = useSession((s) => s.status);
  const sesionExpirada = useSession((s) => s.expired);
  const [params] = useSearchParams();

  if (status === "loading") return <BootScreen />;
  if (status === "authenticated") return <Navigate to={safeNext(params.get("next"))} replace />;

  const expirada = params.get("expired") === "1" || sesionExpirada;

  return (
    <div className="grid min-h-svh bg-background lg:grid-cols-2">
      <BrandPanel />
      <main className="flex flex-col items-center justify-center px-5 py-10 sm:px-8">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 lg:hidden">
            <img
              src="/logo.png"
              alt={`Logo de ${STORE_NAME}`}
              width={72}
              height={68}
              className="size-[4.5rem] rounded-2xl object-cover"
            />
            <span className="text-xl font-semibold tracking-tight">{STORE_NAME}</span>
          </div>
          <div className="mb-8 space-y-2">
            <h1 className="text-[1.75rem] leading-tight font-semibold tracking-tight">Ingresá a {STORE_NAME}</h1>
            <p className="text-sm text-muted-foreground">Usá el email y la contraseña de tu usuario.</p>
          </div>
          {expirada && (
            <Alert className="mb-6 border-warning/40 bg-warning-soft text-foreground">
              <Info aria-hidden="true" className="text-warning" />
              <AlertDescription className="text-foreground">
                <p>
                  <strong className="font-semibold">Tu sesión expiró.</strong> Volvé a ingresar para continuar.
                </p>
              </AlertDescription>
            </Alert>
          )}
          <LoginForm />
        </div>
      </main>
    </div>
  );
}
