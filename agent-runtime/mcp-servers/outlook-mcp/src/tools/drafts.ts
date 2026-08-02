import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { createDraft, listDrafts, updateDraft } from "../graph-client.js";
import { getOutlookAccessToken, ingestDraft } from "../token-broker-client.js";

/**
 * Deliberately no `send_draft` / `send_message` tool is registered anywhere
 * in this MCP server. This is a structural control, not just a skill
 * instruction: the agent has no tool call available that could send mail.
 * Only the control plane, after human approval, calls the Graph send API.
 */
export function registerDraftTools(server: McpServer) {
  server.tool(
    "create_draft",
    "Create an Outlook draft reply. Does NOT send anything — the draft is queued for human review in the dashboard.",
    {
      to: z.string(),
      subject: z.string(),
      body: z.string(),
      threadId: z.string().optional(),
      inReplyToMessageId: z.string().optional(),
      createdBySkill: z.string().default("draft-reply"),
    },
    async ({ to, subject, body, threadId, inReplyToMessageId, createdBySkill }) => {
      const tokenInfo = await getOutlookAccessToken();
      const draft = await createDraft({ to, subject, body, inReplyToMessageId });

      await ingestDraft({
        mailbox_connection_id: tokenInfo.mailbox_connection_id,
        provider_draft_id: draft.id,
        thread_id: draft.conversationId ?? threadId ?? "",
        subject,
        snippet: body.slice(0, 200),
        created_by_skill: createdBySkill,
      });

      return { content: [{ type: "text", text: JSON.stringify(draft) }] };
    }
  );

  server.tool(
    "update_draft",
    "Update the content of an existing Outlook draft.",
    { draftId: z.string(), subject: z.string(), body: z.string() },
    async ({ draftId, subject, body }) => {
      const draft = await updateDraft(draftId, { subject, body });
      return { content: [{ type: "text", text: JSON.stringify(draft) }] };
    }
  );

  server.tool(
    "list_drafts",
    "List existing Outlook drafts.",
    { maxResults: z.number().int().min(1).max(100).optional() },
    async ({ maxResults }) => {
      const result = await listDrafts(maxResults ?? 20);
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );
}
