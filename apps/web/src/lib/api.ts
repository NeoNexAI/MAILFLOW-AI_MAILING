/** Cliente HTTP tipado del API MailFlow. */
import { API_KEY, API_URL } from "./config";
import type {
  Cycle,
  CycleEnqueued,
  EmailAccount,
  EmailAccountCreate,
  LLMProvider,
  LLMProviderCreate,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (API_KEY) headers["X-API-Key"] = API_KEY;

  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const body = text ? JSON.parse(text) : undefined;

  if (!res.ok) {
    const detail =
      (body && (body.detail as string)) || res.statusText || "request failed";
    throw new ApiError(res.status, detail);
  }
  return body as T;
}

export const api = {
  health: () => request<{ status: string; db: string }>("/health"),

  // Email accounts
  listAccounts: () => request<EmailAccount[]>("/accounts"),
  getAccount: (id: string) => request<EmailAccount>(`/accounts/${id}`),
  createAccount: (payload: EmailAccountCreate) =>
    request<EmailAccount>("/accounts", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  deleteAccount: (id: string) =>
    request<void>(`/accounts/${id}`, { method: "DELETE" }),

  // LLM providers
  listProviders: () => request<LLMProvider[]>("/llm-providers"),
  createProvider: (payload: LLMProviderCreate) =>
    request<LLMProvider>("/llm-providers", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Cycles
  listCycles: (accountId: string) =>
    request<Cycle[]>(`/accounts/${accountId}/cycles`),
  runCycle: (accountId: string) =>
    request<CycleEnqueued>(`/accounts/${accountId}/cycles/run`, {
      method: "POST",
    }),
};
