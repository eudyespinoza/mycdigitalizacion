export type SupportCaseKind = "consultation" | "problem";

export type SupportCaseStatus = "new" | "waiting_customer" | "waiting_staff" | "resolved" | "closed";

export type SupportAttachment = {
  public_id: string;
  original_name: string;
  detected_mime_type: string;
  size_bytes: number;
  image_width: number | null;
  image_height: number | null;
  preview_url: string | null;
};

export type SupportMessage = {
  id: number;
  author_role: "customer" | "guest" | "staff";
  body: string;
  created_at: string;
  attachments: SupportAttachment[];
};

export type SupportCaseSummary = {
  public_id: string;
  case_number: string;
  kind: SupportCaseKind;
  subject: string;
  category: string;
  status: SupportCaseStatus;
  updated_at: string;
};

export type SupportCaseDetail = SupportCaseSummary & {
  created_at: string;
  messages: SupportMessage[];
  recovery_code?: string;
};

export type SupportConfiguration = {
  authenticated: boolean;
  email_available: boolean;
  categories: Record<SupportCaseKind, string[]>;
  limits: {
    max_files: number;
    max_file_size_bytes: number;
    max_total_size_bytes: number;
  };
};

export type CreateSupportCaseInput = {
  kind: SupportCaseKind;
  subject: string;
  category: string;
  body: string;
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;
  order?: string;
  product?: string;
  source_url?: string;
  attachments?: File[];
  idempotency_key: string;
};
