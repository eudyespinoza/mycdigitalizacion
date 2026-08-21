import { LoginForm } from "@/components/account/auth-forms";
import { serverGet } from "@/lib/api";
import type { AuthConfiguration } from "@/lib/types";

const fallback: AuthConfiguration = { email_verification_required: true, google_enabled: false, google_client_id: "" };

export default async function LoginPage() {
  const authConfiguration = await serverGet<AuthConfiguration>("/auth/config/").catch(() => fallback);
  return <div className="auth-page"><div><h1>Ingresá a tu cuenta</h1><p>Accedé con tu email y contraseña o usá Google para ver tus pedidos y continuar tu compra.</p></div><LoginForm authConfiguration={authConfiguration} /></div>;
}
