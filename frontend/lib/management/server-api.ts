import "server-only";

import { headers } from "next/headers";


const SERVER_API_ROOT = process.env.API_INTERNAL_URL ?? "http://backend:8000/api/v1";


export class ManagementServerError extends Error {
  constructor(public status: number) {
    super("No se pudo cargar el panel de gestión.");
  }
}


export async function managementServerGet<T>(path: string): Promise<T> {
  const requestHeaders = await headers();
  const response = await fetch(`${SERVER_API_ROOT}/management${path}`, {
    cache: "no-store",
    headers: {
      cookie: requestHeaders.get("cookie") ?? "",
      "X-Forwarded-Proto": "https",
    },
  });
  if (!response.ok) throw new ManagementServerError(response.status);
  return response.json() as Promise<T>;
}
