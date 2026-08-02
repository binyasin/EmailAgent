import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { createDraft, listDrafts, updateDraft } from "../gmail-client.js";
import { getGmailAccessToken, ingestDraft } from "../token-broker-client.js";

/**
 * Deliberately no `send_draft` / `send_message` tool is registered anywhere
 * in this MCP server. This is a structural control, not just a skill
 * instruction: the agent has no tool call available that could send mail.
 * Only the control plane, after human approval, calls the Gmail send API.
 */
export function registerDraftTools(server: McpServer) {
  server.tool(
    "create_draft",
    "Create a Gmail draft reply. Does NOT send anything — the draft is queued for human review in the dashboard.",
    {
      to: z.string(),
      subject: z.string(),
      body: z.string(),
      threadId: z.string().optional(),
      inReplyToMessageId: z.string().optional(),
      createdBySkill: z.string().default("draft-reply"),
    },
    async ({ to, subject, body, threadId, inReplyToMessageId, createdBySkill }) => {
      const tokenInfo = await getGmailAccessToken();
      const draft = await createDraft({ to, subject, body, threadId, inReplyTo: inReplyToMessageId });

      await ingestDraft({
        mailbox_connection_id: tokenInfo.mailbox_connection_id,
        provider_draft_id: draft.id,
        thread_id: draft.message?.threadId ?? threadId ?? "",
        subject,
        snippet: body.slice(0, 200),
        created_by_skill: createdBySkill,
      });

      return { content: [{ type: "text", text: JSON.stringify(draft) }] };
    }
  );

  server.tool(
    "update_draft",
    "Update the content of an existing Gmail draft.",
    {
      draftId: z.string(),
      to: z.string(),
      subject: z.string(),
      body: z.string(),
      threadId: z.string().optional(),
      inReplyToMessageId: z.string().optional(),
    },
    async ({ draftId, to, subject, body, threadId, inReplyToMessageId }) => {
      const draft = await updateDraft(draftId, { to, subject, body, threadId, inReplyTo: inReplyToMessageId });
      return { content: [{ type: "text", text: JSON.stringify(draft) }] };
    }
  );

  server.tool(
    "list_drafts",
    "List existing Gmail drafts.",
    { maxResults: z.number().int().min(1).max(100).optional() },
    async ({ maxResults }) => {
      const result = await listDrafts(maxResults ?? 20);
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );
}
