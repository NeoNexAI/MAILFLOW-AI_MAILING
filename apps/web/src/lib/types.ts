/** DTOs del API MailFlow (espejo de apps/api/app/schemas.py). */

export interface EmailAccount {
  id: string;
  org_id: string;
  provider_type: string;
  imap_host: string;
  imap_port: number;
  use_ssl: boolean;
  username: string;
  inbox_folder: string;
  unclassified_folder: string;
  drafts_folder: string;
  interval_minutes: number;
  is_active: boolean;
  last_cycle_at: string | null;
  llm_provider_id: string | null;
  created_at: string;
}

export interface EmailAccountCreate {
  imap_host: string;
  imap_port?: number;
  use_ssl?: boolean;
  username: string;
  password: string;
  interval_minutes?: number;
  llm_provider_id?: string | null;
}

export interface LLMProvider {
  id: string;
  org_id: string;
  label: string;
  type: string;
  base_url: string;
  default_classification_model: string;
  default_generation_model: string;
  is_active: boolean;
  has_api_key: boolean;
  created_at: string;
}

export interface LLMProviderCreate {
  label: string;
  type: string;
  base_url: string;
  api_key?: string | null;
  default_classification_model: string;
  default_generation_model: string;
}

export interface Cycle {
  id: string;
  account_id: string;
  cycle_id: string;
  emails_processed: number;
  drafts_saved: number;
  error_count: number;
  error_detail: string | null;
  duration_ms: number | null;
  created_at: string;
  finalized_at: string | null;
}

export interface CycleEnqueued {
  account_id: string;
  enqueued: boolean;
  job_id: string | null;
}
