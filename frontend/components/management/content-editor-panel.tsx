"use client";

import { useRouter } from "next/navigation";

import { ContentEditor } from "@/components/management/content-editor";
import { managementRequest } from "@/lib/management/api";
import type { ContentKind, ContentPayload, ManagedContent } from "@/lib/management/content-types";


function toFormData(payload: ContentPayload) {
  const form = new FormData();
  for (const [key, value] of Object.entries(payload)) {
    if (value === null) continue;
    if (value instanceof File) form.append(key, value);
    else if (Array.isArray(value)) form.append(key, JSON.stringify(value));
    else form.append(key, String(value));
  }
  return form;
}


export function ContentEditorPanel({ kind, initial }: { kind: ContentKind; initial?: ManagedContent }) {
  const router = useRouter();
  return <ContentEditor kind={kind} initial={initial} onSave={async (payload) => {
    const path = initial ? `/content/${kind}/${initial.id}/` : `/content/${kind}/`;
    await managementRequest(path, { method: initial ? "PATCH" : "POST", body: toFormData(payload) });
    router.push("/gestion/contenido");
    router.refresh();
  }} />;
}
