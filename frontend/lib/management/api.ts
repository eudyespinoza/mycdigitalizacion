import { apiRequest } from "@/lib/api";


export function managementRequest<T>(path: string, init: RequestInit = {}) {
  return apiRequest<T>(`/management${path}`, init);
}
