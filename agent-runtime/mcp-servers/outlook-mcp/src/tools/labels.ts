import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { createLabel, labelMessage, labelThread, listLabels } from "../graph-client.js";

export function registerLabelTools(server: McpServer) {
  server.tool(
    "list_labels",
    "List all Outlook categories (the mailbox's master category list) available to tag mail with.",
    {},
    async () => {
      const result = await listLabels();
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );

  server.tool(
    "create_label",
    "Create a new Outlook category if it doesn't already exist.",
    { name: z.string() },
    async ({ name }) => {
      const result = await createLabel(name);
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );

  server.tool(
    "label_message",
    "Add and/or remove categories on a single message (used for triage classification). Pass category display names.",
    {
      messageId: z.string(),
      addLabelIds: z.array(z.string()).default([]),
      removeLabelIds: z.array(z.string()).default([]),
    },
    async ({ messageId, addLabelIds, removeLabelIds }) => {
      const result = await labelMessage(messageId, addLabelIds, removeLabelIds);
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );

  server.tool(
    "label_thread",
    "Add and/or remove categories across every message in a conversation (used for triage classification).",
    {
      threadId: z.string(),
      addLabelIds: z.array(z.string()).default([]),
      removeLabelIds: z.array(z.string()).default([]),
    },
    async ({ threadId, addLabelIds, removeLabelIds }) => {
      const result = await labelThread(threadId, addLabelIds, removeLabelIds);
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );

  server.tool(
    "apply_sensitive_thread_label",
    "Flag a conversation as containing sensitive/security-relevant content (e.g. suspected phishing, credential or financial requests). Used by the sensitive-content-flagging skill; suppresses auto-drafting on the thread.",
    { threadId: z.string(), reason: z.string().describe("Short human-readable reason for the flag") },
    async ({ threadId, reason }) => {
      const result = await labelThread(threadId, ["AI/Sensitive"]);
      return { content: [{ type: "text", text: JSON.stringify({ ...result, reason }) }] };
    }
  );
}
