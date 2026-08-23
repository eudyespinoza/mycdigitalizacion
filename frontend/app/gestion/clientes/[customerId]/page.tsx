import { CustomerDetailPanel } from "@/components/management/customer-detail-panel";
import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementCustomerDetail } from "@/lib/management/operations-types";


export default async function ManagementCustomerPage({ params }: { params: Promise<{ customerId: string }> }) {
  const { customerId } = await params;
  const customer = await managementServerGet<ManagementCustomerDetail>(`/customers/${customerId}/`);
  return <CustomerDetailPanel initial={customer} />;
}
