"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ApiError, apiRequest } from "@/lib/api";
import type { Customer } from "@/lib/types";
import { validateEmail, validateVerificationCode } from "@/lib/validation";

function FieldError({ message }: { message?: string }) { return message ? <span className="field-error" role="alert">{message}</span> : null; }

export function LoginForm() {
  const router = useRouter(); const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const submit = async (event: React.FormEvent) => { event.preventDefault(); const invalid = validateEmail(email); if (invalid) { setError(invalid); return; } setBusy(true); setError(""); try { await apiRequest<Customer>("/auth/login/", { method: "POST", body: JSON.stringify({ email, password, cart_token: sessionStorage.getItem("myc-cart-token") || undefined }) }); router.push("/cuenta"); router.refresh(); } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos ingresar."); } finally { setBusy(false); } };
  return <form className="form-stack" onSubmit={(event) => void submit(event)} noValidate><label htmlFor="login-email">Email</label><input id="login-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required /><label htmlFor="login-password">Contraseña</label><input id="login-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required /><FieldError message={error} /><button className="button primary wide" disabled={busy}>{busy ? "Ingresando…" : "Ingresar"}</button><p>¿No tenés cuenta? <Link href="/cuenta/registro">Creala ahora</Link></p></form>;
}

export function RegisterForm() {
  const router = useRouter(); const [values, setValues] = useState({ email: "", password: "", consent: false }); const [errors, setErrors] = useState<Record<string, string>>({}); const [busy, setBusy] = useState(false);
  const submit = async (event: React.FormEvent) => { event.preventDefault(); const nextErrors: Record<string, string> = {}; const emailError = validateEmail(values.email); if (emailError) nextErrors.email = emailError; if (values.password.length < 8) nextErrors.password = "Usá al menos 8 caracteres."; if (!values.consent) nextErrors.consent = "Necesitamos tu aceptación para crear la cuenta."; setErrors(nextErrors); if (Object.keys(nextErrors).length) return; setBusy(true); try { await apiRequest<Customer>("/auth/register/", { method: "POST", body: JSON.stringify({ email: values.email, password: values.password, consent_version: "privacy-v1" }) }); router.push(`/cuenta/verificar?email=${encodeURIComponent(values.email)}`); } catch (cause) { if (cause instanceof ApiError) setErrors({ form: cause.message, ...Object.fromEntries(Object.entries(cause.fields).map(([key, value]) => [key, value[0]])) }); } finally { setBusy(false); } };
  return <form className="form-stack" onSubmit={(event) => void submit(event)} noValidate><label htmlFor="register-email">Email</label><input id="register-email" type="email" autoComplete="email" value={values.email} onChange={(event) => setValues({ ...values, email: event.target.value })} /><FieldError message={errors.email} /><label htmlFor="register-password">Contraseña</label><input id="register-password" type="password" autoComplete="new-password" value={values.password} onChange={(event) => setValues({ ...values, password: event.target.value })} /><span className="helper">Mínimo 8 caracteres. Evitá claves comunes o solo numéricas.</span><FieldError message={errors.password} /><label className="check-label"><input type="checkbox" checked={values.consent} onChange={(event) => setValues({ ...values, consent: event.target.checked })} /> Acepto la política de privacidad vigente.</label><FieldError message={errors.consent} /><FieldError message={errors.form} /><button className="button primary wide" disabled={busy}>{busy ? "Creando cuenta…" : "Crear cuenta"}</button></form>;
}

export function VerifyForm({ initialEmail }: { initialEmail: string }) {
  const router = useRouter(); const [email, setEmail] = useState(initialEmail); const [code, setCode] = useState(""); const [error, setError] = useState(""); const [busy, setBusy] = useState(false);
  const submit = async (event: React.FormEvent) => { event.preventDefault(); const codeError = validateVerificationCode(code); if (codeError) { setError(codeError); return; } setBusy(true); setError(""); try { await apiRequest<{ status: string }>("/auth/email-verify/", { method: "POST", body: JSON.stringify({ email, code }) }); router.push("/cuenta/ingresar"); } catch (cause) { setError(cause instanceof Error ? cause.message : "No pudimos verificar el email."); } finally { setBusy(false); } };
  return <form className="form-stack" onSubmit={(event) => void submit(event)} noValidate><label htmlFor="verify-email">Email</label><input id="verify-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} /><label htmlFor="verify-code">Código de 6 dígitos</label><input id="verify-code" inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(event) => setCode(event.target.value.replace(/\s/g, ""))} /><FieldError message={error} /><button className="button primary wide" disabled={busy}>{busy ? "Verificando…" : "Verificar email"}</button></form>;
}
