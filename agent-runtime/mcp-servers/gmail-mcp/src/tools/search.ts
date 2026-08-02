import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { getMessage, getThread, searchThreads } from "../gmail-client.js";

export function registerSearchTools(server: McpServer) {
  server.tool(
    "search_threads",
    "Search Gmail threads using Gmail search syntax (e.g. 'is:unread newer_than:1d').",
    { query: z.string().describe("Gmail search query"), maxResults: z.number().int().min(1).max(100).optional() },
    async ({ query, maxResults }) => {
      const result = await searchThreads(query, maxResults ?? 20);
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );

  server.tool(
    "get_message",
    "Fetch a single Gmail message (full format, including headers and body) by id.",
    { messageId: z.string() },
    async ({ messageId }) => {
      const result = await getMessage(messageId);
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );

  server.tool(
    "get_thread",
    "Fetch a full Gmail thread (all messages) by thread id.",
    { threadId: z.string() },
    async ({ threadId }) => {
      const result = await getThread(threadId);
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );
}
