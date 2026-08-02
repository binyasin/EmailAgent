const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

function getStoredToken(): string | null {
  return localStorage.getItem("access_token");
}

export function setStoredToken(token: string) {
  localStorage.setItem("access_token", token);
}

export interface CurrentUserClaims {
  sub: string;
  org_id: string | null;
  role: "platform_admin" | "org_admin" | "member";
}

/** Decodes the JWT payload client-side purely for UI gating (which nav
 * links/buttons to show) — the server independently enforces real
 * authorization on every request regardless of what this returns. */
export function getCurrentUserClaims(): CurrentUserClaims | null {
  const token = getStoredToken();
  if (!token) return null;
  try {
    const payload = token.split(".")[1];
    return JSON.parse(atob(payload.replace(/-/g, "+").replace(/_/g, "/")));
  } catch {
    return null;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${init.method ?? "GET"} ${path} failed: ${res.status} ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export interface Draft {
  id: string;
  mailbox_connection_id: string;
  provider_draft_id: string;
  thread_id: string;
  subject: string;
  snippet: string;
  status: string;
  created_by_skill: string;
  created_at: string;
}

export interface MailboxConnection {
  id: string;
  provider: string;
  email_address: string;
  status: string;
  created_at: string;
}

export interface DigestRun {
  id: string;
  period: string;
  summary_text: string;
  created_at: string;
}

export const KNOWN_SKILL_NAMES = [
  "triage",
  "draft-reply",
  "digest",
  "scheduling",
  "followup-nudge",
  "vip-escalation",
  "unsubscribe-cleanup",
  "sensitive-content-flagging",
] as const;

export interface OrgSkillSetting {
  id: string;
  skill_name: string;
  enabled: boolean;
  params: Record<string, unknown>;
  created_at: string;
}

export interface VipRule {
  id: string;
  sender_pattern: string;
  priority: number;
  created_at: string;
}

export interface AgentCell {
  id: string;
  org_id: string;
  tenant_key: string;
  status: string;
  image_ref: string;
  host_port: number | null;
  config_version: number;
  created_at: string;
}

export interface OrgMember {
  id: string;
  email: string;
  role: string;
  created_at: string;
}

export const api = {
  login: (email: string, password: string) =>
    request<{ access_token: string; token_type: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  listDrafts: (statusFilter?: string) =>
    request<Draft[]>(`/drafts${statusFilter ? `?status_filter=${statusFilter}` : ""}`),

  approveDraft: (draftId: string) =>
    request<Draft>(`/drafts/${draftId}/approve`, { method: "POST", body: JSON.stringify({}) }),

  rejectDraft: (draftId: string) =>
    request<Draft>(`/drafts/${draftId}/reject`, { method: "POST" }),

  listMailboxes: () => request<MailboxConnection[]>("/mailboxes"),

  startGmailOAuth: () =>
    request<{ authorization_url: string }>("/mailboxes/gmail/oauth/start"),

  startOutlookOAuth: () =>
    request<{ authorization_url: string }>("/mailboxes/outlook/oauth/start"),

  listDigests: () => request<DigestRun[]>("/digests"),

  listSkillSettings: () => request<OrgSkillSetting[]>("/skill-settings"),

  updateSkillSetting: (skillName: string, enabled: boolean, params: Record<string, unknown> = {}) =>
    request<OrgSkillSetting>(`/skill-settings/${skillName}`, {
      method: "PUT",
      body: JSON.stringify({ enabled, params }),
    }),

  listVipRules: () => request<VipRule[]>("/vip-rules"),

  createVipRule: (senderPattern: string, priority = 0) =>
    request<VipRule>("/vip-rules", {
      method: "POST",
      body: JSON.stringify({ sender_pattern: senderPattern, priority }),
    }),

  deleteVipRule: (ruleId: string) =>
    request<void>(`/vip-rules/${ruleId}`, { method: "DELETE" }),

  listCells: () => request<AgentCell[]>("/cells"),

  getMyCell: () => request<AgentCell>("/cells/mine"),

  provisionMyCell: () => request<AgentCell>("/cells/mine/provision", { method: "POST" }),

  restartCell: (orgId: string) =>
    request<AgentCell>(`/cells/${orgId}/restart`, { method: "POST" }),

  listMembers: () => request<OrgMember[]>("/orgs/members"),

  inviteMember: (email: string, role: string) =>
    request<{ user: OrgMember; temporary_password: string }>("/orgs/invite", {
      method: "POST",
      body: JSON.stringify({ email, role }),
    }),

  changeMemberRole: (memberId: string, role: string) =>
    request<OrgMember>(`/orgs/members/${memberId}/role`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),

  removeMember: (memberId: string) =>
    request<void>(`/orgs/members/${memberId}`, { method: "DELETE" }),
};
