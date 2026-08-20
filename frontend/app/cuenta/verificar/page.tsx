import { VerifyForm } from "@/components/account/auth-forms";
export default async function VerifyPage({ searchParams }: { searchParams: Promise<{ email?: string }> }) { const { email = "" } = await searchParams; return <div className="auth-page"><div><h1>Verificá tu email</h1><p>Ingresá el código de seis dígitos que enviamos a tu email.</p></div><VerifyForm initialEmail={email} /></div>; }
