import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { getMessage, getThread, searchThreads } from "../graph-client.js";

export function registerSearchTools(server: McpServer) {
  server.tool(
    "search_threads",
    "Search Outlook messages and group results by conversation (thread).",
    { query: z.string().describe("Free-text search query"), maxResults: z.number().int().min(1).max(100).optional() },
    async ({ query, maxResults }) => {
      const result = await searchThreads(query, maxResults ?? 20);
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );

  server.tool(
    "get_message",
    "Fetch a single Outlook message by id.",
    { messageId: z.string() },
    async ({ messageId }) => {
      const result = await getMessage(messageId);
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );

  server.tool(
    "get_thread",
    "Fetch all messages in an Outlook conversation (thread) by conversation id.",
    { threadId: z.string() },
    async ({ threadId }) => {
      const result = await getThread(threadId);
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );
}
