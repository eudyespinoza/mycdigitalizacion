import type { SupportAttachment, SupportCaseKind, SupportCaseStatus } from "@/lib/support/types";

export type ManagementSupportPriority = "low" | "normal" | "high" | "urgent";

export type ManagementSupportUser = {
  id: number;
  email: string;
  name: string;
};

export type ManagementSupportMessage = {
  id: number;
  author: ManagementSupportUser | null;
  author_role: "customer" | "guest" | "staff";
  body: string;
  created_at: string;
  attachments: SupportAttachment[];
};

export type ManagementSupportCase = {
  public_id: string;
  case_number: string;
  kind: SupportCaseKind;
  subject: string;
  category: string;
  status: SupportCaseStatus;
  priority: ManagementSupportPriority;
  contact_name: string;
  contact_email: string;
  customer: ManagementSupportUser | null;
  assigned_to: ManagementSupportUser | null;
  message_count: number;
  created_at: string;
  updated_at: string;
};

export type ManagementSupportCaseDetail = ManagementSupportCase & {
  contact_phone: string;
  source_url: string;
  order_id: number | null;
  product_id: number | null;
  resolved_at: string | null;
  closed_at: string | null;
  staff_last_read_at: string | null;
  messages: ManagementSupportMessage[];
};

export type ManagementSupportCaseList = {
  count: number;
  next: string | null;
  previous: string | null;
  results: ManagementSupportCase[];
};

export type ManagementSupportFilters = {
  kind?: SupportCaseKind;
  status?: SupportCaseStatus;
  priority?: ManagementSupportPriority;
  assignee?: string;
  pending?: string;
  unread?: string;
  search?: string;
  page?: string;
};
