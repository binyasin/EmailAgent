import { getOutlookAccessToken } from "./token-broker-client.js";

const GRAPH_API_BASE = "https://graph.microsoft.com/v1.0";

async function graphFetch(path: string, init: RequestInit = {}): Promise<any> {
  const { access_token } = await getOutlookAccessToken();
  const res = await fetch(`${GRAPH_API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      Authorization: `Bearer ${access_token}`,
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) {
    throw new Error(`Graph API ${init.method ?? "GET"} ${path} failed: ${res.status} ${await res.text()}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

/** Outlook has no native "thread" object — messages sharing a `conversationId`
 * form a conversation. `threadId` throughout this module is a conversationId. */
export async function searchThreads(query: string, maxResults = 20) {
  const params = new URLSearchParams({
    $search: `"${query}"`,
    $top: String(maxResults),
  });
  const result = await graphFetch(`/me/messages?${params.toString()}`, {
    headers: { ConsistencyLevel: "eventual" },
  });

  const byThread = new Map<string, any[]>();
  for (const message of result.value ?? []) {
    const list = byThread.get(message.conversationId) ?? [];
    list.push(message);
    byThread.set(message.conversationId, list);
  }
  return {
    threads: Array.from(byThread.entries()).map(([conversationId, messages]) => ({
      id: conversationId,
      messages,
    })),
  };
}

export async function getMessage(messageId: string) {
  return graphFetch(`/me/messages/${encodeURIComponent(messageId)}`);
}

export async function getThread(threadId: string) {
  const params = new URLSearchParams({
    $filter: `conversationId eq '${threadId}'`,
    $orderby: "receivedDateTime asc",
  });
  return graphFetch(`/me/messages?${params.toString()}`);
}

export async function listDrafts(maxResults = 20) {
  return graphFetch(`/me/mailFolders/Drafts/messages?$top=${maxResults}`);
}

/** Creates an Outlook draft only — either a draft reply within a thread
 * (via `createReply`) or a new draft message. There is no corresponding
 * `sendDraft`/`sendMessage` export in this module — sending is performed
 * exclusively by the control plane after human approval, never by the agent. */
export async function createDraft(opts: {
  to: string;
  subject: string;
  body: string;
  inReplyToMessageId?: string;
}) {
  if (opts.inReplyToMessageId) {
    const draft = await graphFetch(
      `/me/messages/${encodeURIComponent(opts.inReplyToMessageId)}/createReply`,
      { method: "POST", body: JSON.stringify({}) }
    );
    return graphFetch(`/me/messages/${encodeURIComponent(draft.id)}`, {
      method: "PATCH",
      body: JSON.stringify({ subject: opts.subject, body: { contentType: "text", content: opts.body } }),
    });
  }

  return graphFetch("/me/messages", {
    method: "POST",
    body: JSON.stringify({
      subject: opts.subject,
      body: { contentType: "text", content: opts.body },
      toRecipients: [{ emailAddress: { address: opts.to } }],
      isDraft: true,
    }),
  });
}

export async function updateDraft(draftId: string, opts: { subject: string; body: string }) {
  return graphFetch(`/me/messages/${encodeURIComponent(draftId)}`, {
    method: "PATCH",
    body: JSON.stringify({ subject: opts.subject, body: { contentType: "text", content: opts.body } }),
  });
}

export async function listLabels() {
  const result = await graphFetch("/me/outlook/masterCategories");
  return (result.value ?? []).map((c: any) => ({ id: c.displayName, name: c.displayName }));
}

export async function createLabel(name: string) {
  return graphFetch("/me/outlook/masterCategories", {
    method: "POST",
    body: JSON.stringify({ displayName: name, color: "preset0" }),
  });
}

async function patchCategories(messageId: string, addLabelIds: string[], removeLabelIds: string[]) {
  const current = await graphFetch(`/me/messages/${encodeURIComponent(messageId)}`);
  const existing: string[] = current.categories ?? [];
  const next = Array.from(new Set([...existing.filter((c) => !removeLabelIds.includes(c)), ...addLabelIds]));
  return graphFetch(`/me/messages/${encodeURIComponent(messageId)}`, {
    method: "PATCH",
    body: JSON.stringify({ categories: next }),
  });
}

/** Outlook categories are free-text strings, not opaque label ids — callers
 * pass category display names directly as `addLabelIds`/`removeLabelIds`
 * (matching the shape of the gmail-mcp tool for skill portability). */
export async function labelMessage(messageId: string, addLabelIds: string[], removeLabelIds: string[] = []) {
  return patchCategories(messageId, addLabelIds, removeLabelIds);
}

export async function labelThread(threadId: string, addLabelIds: string[], removeLabelIds: string[] = []) {
  const thread = await getThread(threadId);
  const results = [];
  for (const message of thread.value ?? []) {
    results.push(await patchCategories(message.id, addLabelIds, removeLabelIds));
  }
  return { updated: results.length };
}
