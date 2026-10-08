import { zodResolver } from "@hookform/resolvers/zod";
import { Eye, EyeOff, TriangleAlert } from "lucide-react";
import { type ReactElement, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { describeLoginError } from "@/features/auth/loginErrors";
import { useSession } from "@/features/auth/session";

const loginSchema = z.object({
  email: z.string().trim().min(1, "Ingresá tu email").email("Ingresá un email válido"),
  password: z.string().min(1, "Ingresá tu contraseña"),
});

type LoginValues = z.infer<typeof loginSchema>;

/** Formulario de acceso: react-hook-form + zod; errores del servidor en linea (UX9). */
export function LoginForm(): ReactElement {
  const login = useSession((s) => s.login);
  const [mostrarClave, setMostrarClave] = useState(false);
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  async function onSubmit(values: LoginValues): Promise<void> {
    setErrorGeneral(null);
    try {
      await login({ email: values.email.trim(), password: values.password });
      // La redireccion la resuelve LoginPage al pasar a "authenticated".
    } catch (error) {
      const fallo = describeLoginError(error);
      setErrorGeneral(fallo.message);
      if (fallo.fields.email !== undefined) setError("email", { message: fallo.fields.email });
      if (fallo.fields.password !== undefined) setError("password", { message: fallo.fields.password });
    }
  }

  return (
    <form noValidate onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      {errorGeneral !== null && (
        <Alert variant="destructive">
          <TriangleAlert aria-hidden="true" />
          <AlertDescription className="text-destructive">{errorGeneral}</AlertDescription>
        </Alert>
      )}
      <FieldGroup className="gap-5">
        <Field data-invalid={errors.email !== undefined}>
          <FieldLabel htmlFor="login-email">Email</FieldLabel>
          <Input
            id="login-email"
            type="email"
            autoComplete="username"
            autoFocus
            inputMode="email"
            placeholder="tu@email.com"
            className="h-11 text-base"
            aria-invalid={errors.email !== undefined}
            aria-describedby={errors.email === undefined ? undefined : "login-email-error"}
            {...register("email")}
          />
          <FieldError id="login-email-error">{errors.email?.message}</FieldError>
        </Field>
        <Field data-invalid={errors.password !== undefined}>
          <FieldLabel htmlFor="login-password">Contraseña</FieldLabel>
          <div className="relative">
            <Input
              id="login-password"
              type={mostrarClave ? "text" : "password"}
              autoComplete="current-password"
              className="h-11 pr-12 text-base"
              aria-invalid={errors.password !== undefined}
              aria-describedby={errors.password === undefined ? undefined : "login-password-error"}
              {...register("password")}
            />
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="absolute top-1/2 right-1 size-9 -translate-y-1/2 text-muted-foreground"
              aria-label={mostrarClave ? "Ocultar contraseña" : "Mostrar contraseña"}
              aria-pressed={mostrarClave}
              onClick={() => setMostrarClave((v) => !v)}
            >
              {mostrarClave ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
            </Button>
          </div>
          <FieldError id="login-password-error">{errors.password?.message}</FieldError>
        </Field>
      </FieldGroup>
      <Button type="submit" size="lg" className="h-11 w-full text-base" disabled={isSubmitting}>
        {isSubmitting && <Spinner aria-hidden="true" />}
        {isSubmitting ? "Ingresando…" : "Ingresar"}
      </Button>
    </form>
  );
}
