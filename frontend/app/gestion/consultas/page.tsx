import { ManagementSupportInbox } from "@/components/management/support-inbox";
import type { ManagementStaffUser } from "@/lib/management/access-types";
import { managementServerGet, managementServerGetOr } from "@/lib/management/server-api";
import type { ManagementSupportCaseList, ManagementSupportFilters } from "@/lib/management/support-types";

export default async function ManagementSupportPage({ searchParams }: { searchParams: Promise<ManagementSupportFilters> }) {
  const filters = await searchParams;
  const query = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => { if (value) query.set(key, value); });
  const [data, users] = await Promise.all([
    managementServerGet<ManagementSupportCaseList>(`/support/cases/${query.size ? `?${query}` : ""}`),
    managementServerGetOr<{ results: ManagementStaffUser[] }>("/users/", { results: [] }),
  ]);
  return <div className="management-page"><ManagementSupportInbox assignees={users.results} initialData={data} initialFilters={filters} /></div>;
}
