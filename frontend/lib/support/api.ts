import { apiRequest } from "@/lib/api";
import type {
  CreateSupportCaseInput,
  SupportCaseDetail,
  SupportCaseSummary,
  SupportConfiguration,
} from "./types";

type CaseListResponse = { results?: SupportCaseSummary[] } | SupportCaseSummary[];

function appendIfPresent(form: FormData, name: string, value: string | undefined) {
  if (value?.trim()) form.append(name, value.trim());
}

export function createSupportIdempotencyKey() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  if (typeof crypto !== "undefined" && typeof crypto.getRandomValues === "function") {
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  }
  throw new Error("No pudimos preparar el envío. Actualizá el navegador e intentá nuevamente.");
}

function createFormData(input: CreateSupportCaseInput) {
  const form = new FormData();
  form.append("kind", input.kind);
  form.append("subject", input.subject.trim());
  form.append("category", input.category);
  form.append("body", input.body.trim());
  form.append("idempotency_key", input.idempotency_key);
  appendIfPresent(form, "contact_name", input.contact_name);
  appendIfPresent(form, "contact_email", input.contact_email);
  appendIfPresent(form, "contact_phone", input.contact_phone);
  appendIfPresent(form, "order", input.order);
  appendIfPresent(form, "product", input.product);
  appendIfPresent(form, "source_url", input.source_url);
  input.attachments?.forEach((attachment) => form.append("attachments", attachment));
  return form;
}

export const supportApi = {
  configuration: () => apiRequest<SupportConfiguration>("/support/configuration/"),
  listCases: async () => {
    const response = await apiRequest<CaseListResponse>("/support/cases/");
    return Array.isArray(response) ? response : response.results ?? [];
  },
  createCase: (input: CreateSupportCaseInput) => apiRequest<SupportCaseDetail>("/support/cases/", {
    method: "POST",
    body: createFormData(input),
  }),
  recoverCase: (caseNumber: string, code: string) => apiRequest<SupportCaseDetail>("/support/access/", {
    method: "POST",
    body: JSON.stringify({ case_number: caseNumber.trim(), code }),
  }),
};
