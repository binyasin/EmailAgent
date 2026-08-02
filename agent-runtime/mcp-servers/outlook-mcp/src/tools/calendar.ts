import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { createTentativeEvent, findAvailability, listEvents } from "../calendar-client.js";

export function registerCalendarTools(server: McpServer) {
  server.tool(
    "find_availability",
    "Check free/busy schedule for one or more mailboxes within a time range (ISO 8601 datetimes).",
    { schedules: z.array(z.string()).describe("Email addresses to check"), startIso: z.string(), endIso: z.string() },
    async ({ schedules, startIso, endIso }) => {
      const result = await findAvailability(schedules, startIso, endIso);
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );

  server.tool(
    "list_events",
    "List calendar events within a time range (ISO 8601 datetimes).",
    { startIso: z.string(), endIso: z.string() },
    async ({ startIso, endIso }) => {
      const result = await listEvents(startIso, endIso);
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );

  server.tool(
    "create_event",
    "Create a TENTATIVE calendar event (showAs: tentative) on the user's own calendar, without inviting attendees. Confirm via create_draft instead, subject to human approval.",
    {
      subject: z.string(),
      bodyText: z.string().optional(),
      startIso: z.string().describe("ISO 8601 start datetime"),
      endIso: z.string().describe("ISO 8601 end datetime"),
      timeZone: z.string().describe("IANA or Windows timezone name, e.g. 'Eastern Standard Time'"),
    },
    async ({ subject, bodyText, startIso, endIso, timeZone }) => {
      const result = await createTentativeEvent({ subject, bodyText, startIso, endIso, timeZone });
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );
}
