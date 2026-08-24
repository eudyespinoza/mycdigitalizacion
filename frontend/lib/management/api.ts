import { apiRequest } from "@/lib/api";


export function managementRequest<T>(path: string, init: RequestInit = {}) {
  return apiRequest<T>(`/management${path}`, init);
}


export function managementSupportAttachmentDownloadUrl(publicId: string, preview = false) {
  return `/api/v1/management/support/attachments/${publicId}/${preview ? "?preview=1" : ""}`;
}
