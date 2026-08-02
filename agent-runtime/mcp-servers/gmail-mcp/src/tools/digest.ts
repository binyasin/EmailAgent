import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { config } from "../config.js";

async function ingestDigest(period: "daily" | "weekly", summaryText: string): Promise<void> {
  const url = new URL("/internal/v1/digests/ingest", config.controlPlaneInternalUrl);
  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Cell-Service-Token": config.cellServiceToken,
    },
    body: JSON.stringify({ period, summary_text: summaryText }),
  });
  if (!res.ok) {
    throw new Error(`digest ingest failed: ${res.status} ${await res.text()}`);
  }
}

export function registerDigestTools(server: McpServer) {
  server.tool(
    "notify_digest_ready",
    "Store an assembled daily/weekly digest summary so it appears in the dashboard's Digest view. Does not send email.",
    { period: z.enum(["daily", "weekly"]), summaryText: z.string() },
    async ({ period, summaryText }) => {
      await ingestDigest(period, summaryText);
      return { content: [{ type: "text", text: "digest stored" }] };
    }
  );
}
