import type { Cart } from "@/lib/types";

const PUBLIC_API_ROOT = "/api/v1";
const SERVER_API_ROOT = process.env.API_INTERNAL_URL ?? "http://backend:8000/api/v1";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);
const ROTATING_AUTH_PATHS = new Set(["/auth/login/", "/auth/logout/"]);

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public fields: Record<string, string[]> = {},
  ) {
    super(message);
  }
}

function normalizeError(status: number, body: unknown) {
  if (body && typeof body === "object") {
    const record = body as Record<string, unknown>;
    if (typeof record.detail === "string") return new ApiError(status, String(record.code ?? "request_failed"), record.detail);
    const fields = Object.fromEntries(Object.entries(record).map(([key, value]) => [key, Array.isArray(value) ? value.map(String) : [String(value)]]));
    return new ApiError(status, "validation_error", "Revisá los datos ingresados.", fields);
  }
  return new ApiError(status, "request_failed", "No pudimos completar la solicitud.");
}

async function readBody(response: Response) {
  if (response.status === 204) return undefined;
  return response.json().catch(() => null);
}

async function parse<T>(response: Response): Promise<T> {
  const body = await readBody(response);
  if (!response.ok) throw normalizeError(response.status, body);
  return body as T;
}

export function normalizeMediaUrl(value: string | null | undefined) {
  if (!value) return "";
  if (value.startsWith("/")) return value;
  try {
    const url = new URL(value);
    return url.pathname.startsWith("/media/") ? `${url.pathname}${url.search}` : "";
  } catch {
    return "";
  }
}

export async function serverGet<T>(path: string): Promise<T> {
  const response = await fetch(`${SERVER_API_ROOT}${path}`, { cache: "no-store" });
  return parse<T>(response);
}

let csrfToken = "";
export function clearCsrfToken() { csrfToken = ""; }

async function csrf() {
  if (csrfToken) return csrfToken;
  const response = await fetch(`${PUBLIC_API_ROOT}/auth/csrf/`, { credentials: "include" });
  const body = await parse<{ csrf_token: string }>(response);
  csrfToken = body.csrf_token;
  return csrfToken;
}

function isNamedCsrfFailure(status: number, body: unknown) {
  if (status !== 403 || !body || typeof body !== "object") return false;
  const record = body as Record<string, unknown>;
  return record.code === "csrf_failed" || record.code === "csrf_failure" ||
    (typeof record.detail === "string" && /csrf/i.test(record.detail));
}

export async function apiRequest<T>(path: string, init: RequestInit = {}, cartToken?: string | null): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const unsafe = !SAFE_METHODS.has(method);
  const send = async (retried: boolean): Promise<T> => {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body) headers.set("Content-Type", "application/json");
    if (cartToken) headers.set("X-Cart-Token", cartToken);
    if (unsafe) headers.set("X-CSRFToken", await csrf());
    const response = await fetch(`${PUBLIC_API_ROOT}${path}`, { ...init, headers, credentials: "include" });
    const body = await readBody(response);
    if (!response.ok && unsafe && !retried && isNamedCsrfFailure(response.status, body)) {
      clearCsrfToken();
      return send(true);
    }
    if (!response.ok) throw normalizeError(response.status, body);
    if (ROTATING_AUTH_PATHS.has(path)) clearCsrfToken();
    return body as T;
  };
  return send(false);
}

export const cartApi = {
  get: (token?: string | null) => apiRequest<Cart>("/cart/", {}, token),
  add: (payload: { variant_id: number; quantity: number }, token?: string | null) => apiRequest<Cart>("/cart/", { method: "POST", body: JSON.stringify(payload) }, token),
  quantity: (payload: { variant_id: number; quantity: number }, token?: string | null) => apiRequest<Cart>("/cart/", { method: "PATCH", body: JSON.stringify(payload) }, token),
  coupon: (coupon: string, token?: string | null) => apiRequest<Cart>("/cart/", { method: "POST", body: JSON.stringify({ coupon }) }, token),
  clear: (variant_id?: number, token?: string | null) => apiRequest<Cart>("/cart/", { method: "DELETE", body: JSON.stringify(variant_id ? { variant_id } : {}) }, token),
};
