import { ManagementSupportCasePanel } from "@/components/management/support-case-panel";
import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementSupportAssigneeList, ManagementSupportCaseDetail } from "@/lib/management/support-types";

export default async function ManagementSupportCasePage({ params }: { params: Promise<{ publicId: string }> }) {
  const { publicId } = await params;
  const [supportCase, assigneeResult] = await Promise.all([
    managementServerGet<ManagementSupportCaseDetail>(`/support/cases/${publicId}/`),
    managementServerGet<ManagementSupportAssigneeList>("/support/assignees/")
      .then((result) => ({ assignees: result.results, error: "", retryable: true }))
      .catch((cause) => {
        const forbidden = typeof cause === "object" && cause !== null && "status" in cause && cause.status === 403;
        return { assignees: [], error: forbidden ? "No tenés permiso para asignar responsables." : "No pudimos cargar las personas disponibles para asignar. Reintentá.", retryable: !forbidden };
      }),
  ]);
  return <div className="management-page"><ManagementSupportCasePanel initialAssigneeError={assigneeResult.error} initialAssigneeRetryable={assigneeResult.retryable} initialAssignees={assigneeResult.assignees} initialCase={supportCase} /></div>;
}
