"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { GoogleIdentityButton } from "@/components/account/google-identity-button";
import { ApiError, apiRequest } from "@/lib/api";
import type { AuthConfiguration, Customer } from "@/lib/types";
import { validateEmail, validateVerificationCode } from "@/lib/validation";

function FieldError({ id, message }: { id?: string; message?: string }) { return message ? <span id={id} className="field-error" role="alert">{message}</span> : null; }
const focusFirst = (errors: Record<string, string>, prefix: string) => requestAnimationFrame(() => {
  const firstInvalid = document.querySelector<HTMLElement>(`.${prefix}-form [aria-invalid="true"]`);
  (firstInvalid ?? document.getElementById(`${prefix}-${Object.keys(errors)[0]}`))?.focus();
});

const SECURE_AUTH_FALLBACK: AuthConfiguration = {
  email_verification_required: true,
  google_enabled: false,
  google_client_id: "",
};

function googleError(cause: unknown) {
  if (cause instanceof ApiError && cause.code === "google_registration_required") {
    return "Ese email todavía no tiene cuenta. Creala desde Registro con Google.";
  }
  return cause instanceof Error ? cause.message : "No pudimos continuar con Google.";
}

export function LoginForm({ authConfiguration = SECURE_AUTH_FALLBACK }: { authConfiguration?: AuthConfiguration }) {
  const router = useRouter(); const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const submit = async (event: React.FormEvent) => { event.preventDefault(); const invalid = validateEmail(email); if (invalid) { setError(invalid); document.getElementById("login-email")?.focus(); return; } setBusy(true); setError(""); try { await apiRequest<Customer>("/auth/login/", { method: "POST", body: JSON.stringify({ email, password, cart_token: sessionStorage.getItem("myc-cart-token") || undefined }) }); sessionStorage.removeItem("myc-cart-token"); router.push("/cuenta"); router.refresh(); } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos ingresar."); } finally { setBusy(false); } };
  const submitGoogle = async (credential: string) => {
    setBusy(true); setError("");
    try {
      await apiRequest<Customer>("/auth/google/", { method: "POST", body: JSON.stringify({ credential, mode: "login", cart_token: sessionStorage.getItem("myc-cart-token") || undefined }) });
      sessionStorage.removeItem("myc-cart-token"); router.push("/cuenta"); router.refresh();
    } catch (cause) { setError(googleError(cause)); } finally { setBusy(false); }
  };
  return <form className="form-stack" onSubmit={(event) => void submit(event)} noValidate><label htmlFor="login-email">Email</label><input id="login-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} aria-describedby={error ? "login-error" : undefined} required /><label htmlFor="login-password">Contraseña</label><input id="login-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /><FieldError id="login-error" message={error} /><button className="button primary wide" disabled={busy}>{busy ? "Ingresando…" : "Ingresar"}</button>{authConfiguration.google_enabled && authConfiguration.google_client_id ? <><div className="auth-separator"><span>o</span></div><GoogleIdentityButton clientId={authConfiguration.google_client_id} mode="login" onCredential={(credential) => void submitGoogle(credential)} /></> : null}<p>¿No tenés cuenta? <Link href="/cuenta/registro">Creala ahora</Link></p></form>;
}

export function RegisterForm({ authConfiguration = SECURE_AUTH_FALLBACK }: { authConfiguration?: AuthConfiguration }) {
  const router = useRouter(); const [values, setValues] = useState({ email: "", password: "", first_name: "", last_name: "", phone: "", consent: false }); const [errors, setErrors] = useState<Record<string, string>>({}); const [busy, setBusy] = useState(false);
  const validPhone = () => /^[+().\s\-/\d]{6,32}$/.test(values.phone) && (values.phone.match(/\d/g)?.length ?? 0) >= 6;
  const submit = async (event: React.FormEvent) => { event.preventDefault(); const next: Record<string, string> = {}; const emailError = validateEmail(values.email); if (emailError) next.email = emailError; if (!values.first_name.trim()) next.first_name = "Ingresá tu nombre."; if (!values.last_name.trim()) next.last_name = "Ingresá tu apellido."; if (!validPhone()) next.phone = "Ingresá un teléfono válido."; if (values.password.length < 8) next.password = "Usá al menos 8 caracteres."; if (!values.consent) next.consent = "Necesitamos tu aceptación para crear la cuenta."; setErrors(next); if (Object.keys(next).length) { focusFirst(next, "register"); return; } setBusy(true); try { await apiRequest<Customer>("/auth/register/", { method: "POST", body: JSON.stringify({ email: values.email, password: values.password, first_name: values.first_name.trim(), last_name: values.last_name.trim(), phone: values.phone.trim(), consent_version: "privacy-v1" }) }); router.push(authConfiguration.email_verification_required ? `/cuenta/verificar?email=${encodeURIComponent(values.email)}` : "/cuenta/ingresar?registered=1"); } catch (cause) { if (cause instanceof ApiError) { const nextErrors = { form: cause.message, ...Object.fromEntries(Object.entries(cause.fields).map(([key, value]) => [key, value[0]])) }; setErrors(nextErrors); focusFirst(nextErrors, "register"); } else setErrors({ form: "No pudimos crear la cuenta." }); } finally { setBusy(false); } };
  const submitGoogle = async (credential: string) => {
    const next: Record<string, string> = {};
    if (!validPhone()) next.phone = "Ingresá un teléfono válido para crear tu cuenta con Google.";
    if (!values.consent) next.consent = "Necesitamos tu aceptación para crear la cuenta.";
    setErrors(next);
    if (Object.keys(next).length) { focusFirst(next, "register"); return; }
    setBusy(true);
    try {
      await apiRequest<Customer>("/auth/google/", { method: "POST", body: JSON.stringify({ credential, mode: "register", phone: values.phone.trim(), consent_version: "privacy-v1", cart_token: sessionStorage.getItem("myc-cart-token") || undefined }) });
      sessionStorage.removeItem("myc-cart-token"); router.push("/cuenta"); router.refresh();
    } catch (cause) { setErrors({ form: googleError(cause) }); } finally { setBusy(false); }
  };
  const input = (name: "email" | "password" | "first_name" | "last_name" | "phone", label: string, props: React.InputHTMLAttributes<HTMLInputElement>) => <div><label htmlFor={`register-${name}`}>{label}</label><input id={`register-${name}`} value={values[name]} onChange={(event) => setValues({ ...values, [name]: event.target.value })} aria-invalid={Boolean(errors[name])} aria-describedby={errors[name] ? `register-${name}-error` : undefined} {...props} /><FieldError id={`register-${name}-error`} message={errors[name]} /></div>;
  const googleReady = authConfiguration.google_enabled && authConfiguration.google_client_id && validPhone() && values.consent;
  return <form className="form-stack register-form" onSubmit={(event) => void submit(event)} noValidate><div className="field-pair">{input("first_name", "Nombre", { autoComplete: "given-name" })}{input("last_name", "Apellido", { autoComplete: "family-name" })}</div>{input("phone", "Teléfono", { type: "tel", autoComplete: "tel" })}{input("email", "Email", { type: "email", autoComplete: "email" })}{input("password", "Contraseña", { type: "password", autoComplete: "new-password" })}<span className="helper">Mínimo 8 caracteres. Evitá claves comunes o solo numéricas.</span><label className="check-label"><input id="register-consent" type="checkbox" checked={values.consent} onChange={(event) => setValues({ ...values, consent: event.target.checked })} aria-describedby={errors.consent ? "register-consent-error" : undefined} /> Acepto la política de privacidad vigente.</label><FieldError id="register-consent-error" message={errors.consent} /><FieldError message={errors.form} /><button className="button primary wide" disabled={busy}>{busy ? "Creando cuenta…" : "Crear cuenta"}</button>{authConfiguration.google_enabled && authConfiguration.google_client_id ? <><div className="auth-separator"><span>o</span></div>{googleReady ? <GoogleIdentityButton clientId={authConfiguration.google_client_id} mode="register" onCredential={(credential) => void submitGoogle(credential)} /> : <p className="google-auth-helper">Para registrarte con Google, completá el teléfono y aceptá la política de privacidad.</p>}</> : null}</form>;
}

export function VerifyForm({ initialEmail }: { initialEmail: string }) {
  const router = useRouter(); const [email, setEmail] = useState(initialEmail); const [code, setCode] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const submit = async (event: React.FormEvent) => { event.preventDefault(); const codeError = validateVerificationCode(code); if (codeError) { setError(codeError); document.getElementById("verify-code")?.focus(); return; } setBusy(true); setError(""); try { await apiRequest<{ status: string }>("/auth/email-verify/", { method: "POST", body: JSON.stringify({ email, code }) }); router.push("/cuenta/ingresar"); } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos verificar el email."); } finally { setBusy(false); } };
  return <form className="form-stack" onSubmit={(event) => void submit(event)} noValidate><label htmlFor="verify-email">Email</label><input id="verify-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} /><label htmlFor="verify-code">Código de 6 dígitos</label><input id="verify-code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(event) => setCode(event.target.value.replace(/\s/g, ""))} aria-describedby={error ? "verify-error" : undefined} /><FieldError id="verify-error" message={error} /><button className="button primary wide" disabled={busy}>{busy ? "Verificando…" : "Verificar email"}</button></form>;
}
