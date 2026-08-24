import { ManagementSupportCasePanel } from "@/components/management/support-case-panel";
import type { ManagementStaffUser } from "@/lib/management/access-types";
import { managementServerGet, managementServerGetOr } from "@/lib/management/server-api";
import type { ManagementSupportCaseDetail } from "@/lib/management/support-types";

export default async function ManagementSupportCasePage({ params }: { params: Promise<{ publicId: string }> }) {
  const { publicId } = await params;
  const [supportCase, users] = await Promise.all([
    managementServerGet<ManagementSupportCaseDetail>(`/support/cases/${publicId}/`),
    managementServerGetOr<{ results: ManagementStaffUser[] }>("/users/", { results: [] }),
  ]);
  return <div className="management-page"><ManagementSupportCasePanel initialCase={supportCase} staff={users.results} /></div>;
}
