export type ManagementRole = {
  name: string;
  label: string;
  permission_count: number;
};

export type ManagementStaffUser = {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  is_active: boolean;
  is_superuser: boolean;
  role_names: string[];
  last_login: string | null;
};

export type ManagementAuditEvent = {
  id: number;
  actor: string;
  action: string;
  resource: string;
  object_reference: string;
  metadata: Record<string, unknown>;
  created_at: string;
};
