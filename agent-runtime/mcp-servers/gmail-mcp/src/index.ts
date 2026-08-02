#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { registerCalendarTools } from "./tools/calendar.js";
import { registerDigestTools } from "./tools/digest.js";
import { registerDraftTools } from "./tools/drafts.js";
import { registerLabelTools } from "./tools/labels.js";
import { registerSearchTools } from "./tools/search.js";

const server = new McpServer({ name: "gmail-mcp", version: "0.1.0" });

registerSearchTools(server);
registerDraftTools(server);
registerLabelTools(server);
registerCalendarTools(server);
registerDigestTools(server);

const transport = new StdioServerTransport();
await server.connect(transport);
