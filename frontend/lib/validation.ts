export function validateVerificationCode(code: string) {
  return /^\d{6}$/.test(code) ? null : "Ingresá el código de 6 dígitos.";
}

export function validateEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) ? null : "Ingresá un email válido.";
}
