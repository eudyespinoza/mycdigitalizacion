import { ManagementSupportInbox } from "@/components/management/support-inbox";
import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementSupportAssigneeList, ManagementSupportCaseList, ManagementSupportFilters } from "@/lib/management/support-types";

export default async function ManagementSupportPage({ searchParams }: { searchParams: Promise<ManagementSupportFilters> }) {
  const filters = await searchParams;
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value) query.set(key, value); });
  const [data, assigneeResult] = await Promise.all([
    managementServerGet<ManagementSupportCaseList>(`/support/cases/${query.size ? `?${query}` : ""}`),
    managementServerGet<ManagementSupportAssigneeList>("/support/assignees/")
      .then((result) => ({ assignees: result.results, error: "", retryable: true }))
      .catch((cause) => {
        const forbidden = typeof cause === "object" && cause !== null && "status" in cause && cause.status === 403;
        return { assignees: [], error: forbidden ? "No tenés permiso para asignar responsables." : "No pudimos cargar las personas disponibles para asignar. Reintentá.", retryable: !forbidden };
      }),
  ]);
  return <div className="management-page"><ManagementSupportInbox initialAssigneeError={assigneeResult.error} initialAssigneeRetryable={assigneeResult.retryable} initialAssignees={assigneeResult.assignees} initialData={data} initialFilters={filters} /></div>;
}
