import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { describe, expect, it } from "vitest";
import { registerCalendarTools } from "./tools/calendar.js";
import { registerDigestTools } from "./tools/digest.js";
import { registerDraftTools } from "./tools/drafts.js";
import { registerLabelTools } from "./tools/labels.js";
import { registerSearchTools } from "./tools/search.js";

function registeredToolNames(server: McpServer): string[] {
  // @ts-expect-error — reaching into SDK internals is acceptable for this
  // structural safety-net test only.
  return Object.keys(server._registeredTools ?? {});
}

describe("gmail-mcp tool surface", () => {
  it("never registers a send-capable tool", () => {
    const server = new McpServer({ name: "gmail-mcp-test", version: "0.0.0" });
    registerSearchTools(server);
    registerDraftTools(server);
    registerLabelTools(server);
    registerCalendarTools(server);
    registerDigestTools(server);

    const names = registeredToolNames(server);
    const sendLike = names.filter((n) => /send/i.test(n));

    expect(sendLike).toEqual([]);
    expect(names).toEqual(
      expect.arrayContaining(["create_draft", "update_draft", "list_drafts"])
    );
  });
});
