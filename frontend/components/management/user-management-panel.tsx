"use client";

import { useRouter } from "next/navigation";

import { ManagementUserEditor } from "@/components/management/user-editor";
import { ManagementUserTable } from "@/components/management/user-table";
import { managementRequest } from "@/lib/management/api";
import type { ManagementRole, ManagementStaffUser } from "@/lib/management/access-types";


export function UserManagementPanel({ users, roles }: { users: ManagementStaffUser[]; roles: ManagementRole[] }) {
  const router = useRouter();
  return <div className="management-users-layout"><div><ManagementUserTable users={users} /></div><ManagementUserEditor roles={roles} onSave={async (payload) => { await managementRequest("/users/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); router.refresh(); }} /></div>;
}
