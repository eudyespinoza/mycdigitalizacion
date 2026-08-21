import { RegisterForm } from "@/components/account/auth-forms";
import { serverGet } from "@/lib/api";
import type { AuthConfiguration } from "@/lib/types";

const fallback: AuthConfiguration = { email_verification_required: true, google_enabled: false, google_client_id: "" };

export default async function RegisterPage() {
  const authConfiguration = await serverGet<AuthConfiguration>("/auth/config/").catch(() => fallback);
  const copy = authConfiguration.email_verification_required
    ? "Después de registrarte te vamos a pedir un código enviado a tu email."
    : "Tu cuenta queda lista al registrarte. No necesitás validar el email mientras el correo transaccional no esté configurado.";
  return <div className="auth-page"><div><h1>Creá tu cuenta</h1><p>{copy}</p></div><RegisterForm authConfiguration={authConfiguration} /></div>;
}
