import { ManagementSupportCasePanel } from "@/components/management/support-case-panel";
import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementSupportAssigneeList, ManagementSupportCaseDetail } from "@/lib/management/support-types";

export default async function ManagementSupportCasePage({ params }: { params: Promise<{ publicId: string }> }) {
  const { publicId } = await params;
  const [supportCase, assigneeResult] = await Promise.all([
    managementServerGet<ManagementSupportCaseDetail>(`/support/cases/${publicId}/`),
    managementServerGet<ManagementSupportAssigneeList>("/support/assignees/")
      .then((result) => ({ assignees: result.results, error: "" }))
      .catch(() => ({ assignees: [], error: "No pudimos cargar las personas disponibles para asignar. Reintentá." })),
  ]);
  return <div className="management-page"><ManagementSupportCasePanel initialAssigneeError={assigneeResult.error} initialAssignees={assigneeResult.assignees} initialCase={supportCase} /></div>;
}
