import Link from "next/link";

import { SupportCategoryManager } from "@/components/management/support-category-manager";
import { managementServerGet } from "@/lib/management/server-api";
import type { ManagementSupportCategoryList } from "@/lib/management/support-types";

export default async function ManagementSupportCategoriesPage() {
  const categories = await managementServerGet<ManagementSupportCategoryList>("/support/categories/");
  return <div className="management-page"><Link className="management-back" href="/gestion/consultas">← Consultas</Link><SupportCategoryManager initialCategories={categories.results} /></div>;
}
