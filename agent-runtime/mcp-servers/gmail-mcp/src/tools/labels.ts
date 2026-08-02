import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { createLabel, labelMessage, labelThread, listLabels } from "../gmail-client.js";

export function registerLabelTools(server: McpServer) {
  server.tool("list_labels", "List all Gmail labels in the mailbox.", {}, async () => {
    const result = await listLabels();
    return { content: [{ type: "text", text: JSON.stringify(result) }] };
  });

  server.tool(
    "create_label",
    "Create a new Gmail label if it doesn't already exist.",
    { name: z.string() },
    async ({ name }) => {
      const result = await createLabel(name);
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );

  server.tool(
    "label_message",
    "Add and/or remove labels on a single message (used for triage classification).",
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
    "Add and/or remove labels on an entire thread (used for triage classification).",
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
    "Flag a thread as containing sensitive/security-relevant content (e.g. suspected phishing, credential or financial requests). Used by the sensitive-content-flagging skill; suppresses auto-drafting on the thread.",
    { threadId: z.string(), reason: z.string().describe("Short human-readable reason for the flag") },
    async ({ threadId, reason }) => {
      const labels = await listLabels();
      const existing = labels.labels?.find((l: any) => l.name === "AI/Sensitive");
      const labelId = existing?.id ?? (await createLabel("AI/Sensitive")).id;
      const result = await labelThread(threadId, [labelId]);
      return { content: [{ type: "text", text: JSON.stringify({ ...result, reason }) }] };
    }
  );
}
