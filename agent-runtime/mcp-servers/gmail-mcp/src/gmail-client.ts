import { getGmailAccessToken } from "./token-broker-client.js";

const GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me";

async function gmailFetch(path: string, init: RequestInit = {}): Promise<any> {
  const { access_token } = await getGmailAccessToken();
  const res = await fetch(`${GMAIL_API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      Authorization: `Bearer ${access_token}`,
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) {
    throw new Error(`Gmail API ${init.method ?? "GET"} ${path} failed: ${res.status} ${await res.text()}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

function encodeRfc2822Message(opts: {
  to: string;
  subject: string;
  body: string;
  threadId?: string;
  inReplyTo?: string;
}): string {
  const headers = [`To: ${opts.to}`, `Subject: ${opts.subject}`, "Content-Type: text/plain; charset=utf-8"];
  if (opts.inReplyTo) {
    headers.push(`In-Reply-To: ${opts.inReplyTo}`, `References: ${opts.inReplyTo}`);
  }
  const raw = `${headers.join("\r\n")}\r\n\r\n${opts.body}`;
  return Buffer.from(raw).toString("base64url");
}

export async function searchThreads(query: string, maxResults = 20) {
  const params = new URLSearchParams({ q: query, maxResults: String(maxResults) });
  return gmailFetch(`/threads?${params.toString()}`);
}

export async function getMessage(messageId: string) {
  return gmailFetch(`/messages/${encodeURIComponent(messageId)}?format=full`);
}

export async function getThread(threadId: string) {
  return gmailFetch(`/threads/${encodeURIComponent(threadId)}?format=full`);
}

export async function listDrafts(maxResults = 20) {
  return gmailFetch(`/drafts?maxResults=${maxResults}`);
}

/** Creates a Gmail draft only. There is no corresponding `sendDraft`/`sendMessage`
 * export in this module — sending is performed exclusively by the control
 * plane after human approval, never by the agent. */
export async function createDraft(opts: {
  to: string;
  subject: string;
  body: string;
  threadId?: string;
  inReplyTo?: string;
}) {
  const draft = await gmailFetch("/drafts", {
    method: "POST",
    body: JSON.stringify({
      message: {
        raw: encodeRfc2822Message(opts),
        threadId: opts.threadId,
      },
    }),
  });
  return draft;
}

export async function updateDraft(
  draftId: string,
  opts: { to: string; subject: string; body: string; threadId?: string; inReplyTo?: string }
) {
  return gmailFetch(`/drafts/${encodeURIComponent(draftId)}`, {
    method: "PUT",
    body: JSON.stringify({
      message: {
        raw: encodeRfc2822Message(opts),
        threadId: opts.threadId,
      },
    }),
  });
}

export async function listLabels() {
  return gmailFetch("/labels");
}

export async function createLabel(name: string) {
  return gmailFetch("/labels", {
    method: "POST",
    body: JSON.stringify({ name, labelListVisibility: "labelShow", messageListVisibility: "show" }),
  });
}

export async function labelMessage(messageId: string, addLabelIds: string[], removeLabelIds: string[] = []) {
  return gmailFetch(`/messages/${encodeURIComponent(messageId)}/modify`, {
    method: "POST",
    body: JSON.stringify({ addLabelIds, removeLabelIds }),
  });
}

export async function labelThread(threadId: string, addLabelIds: string[], removeLabelIds: string[] = []) {
  return gmailFetch(`/threads/${encodeURIComponent(threadId)}/modify`, {
    method: "POST",
    body: JSON.stringify({ addLabelIds, removeLabelIds }),
  });
}
