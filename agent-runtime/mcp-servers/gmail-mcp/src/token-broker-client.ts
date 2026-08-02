import { config } from "./config.js";

export interface AccessTokenResponse {
  mailbox_connection_id: string;
  provider: string;
  email_address: string;
  access_token: string;
}

/**
 * Fetches a short-lived Gmail access token from the control plane's internal
 * token broker. This server never stores or sees a long-lived refresh token
 * — every tool call re-fetches a fresh access token, so a compromised cell
 * can leak at most one short-lived credential. The control plane derives
 * which org this is for from the token itself (see config.ts) — there is
 * no tenant id parameter to pass (or for a compromised cell to spoof).
 */
export async function getGmailAccessToken(): Promise<AccessTokenResponse> {
  const url = new URL("/internal/v1/tokens/current", config.controlPlaneInternalUrl);
  url.searchParams.set("provider", "gmail");

  const res = await fetch(url, {
    headers: { "X-Cell-Service-Token": config.cellServiceToken },
  });
  if (!res.ok) {
    throw new Error(`token broker request failed: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as AccessTokenResponse;
}

export interface DraftIngestPayload {
  mailbox_connection_id: string;
  provider_draft_id: string;
  thread_id: string;
  subject?: string;
  snippet?: string;
  created_by_skill?: string;
}

/** Notifies the control plane that a new draft exists so it can be surfaced
 * in the human approval inbox. */
export async function ingestDraft(payload: DraftIngestPayload): Promise<void> {
  const url = new URL("/internal/v1/drafts/ingest", config.controlPlaneInternalUrl);
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Cell-Service-Token": config.cellServiceToken,
    },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(`draft ingest failed: ${res.status} ${await res.text()}`);
  }
}
