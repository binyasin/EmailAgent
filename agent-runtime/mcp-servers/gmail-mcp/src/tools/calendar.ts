import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { createTentativeEvent, findAvailability, listEvents } from "../calendar-client.js";

export function registerCalendarTools(server: McpServer) {
  server.tool(
    "find_availability",
    "Check free/busy status on the primary calendar within a time range (ISO 8601 datetimes).",
    { timeMin: z.string(), timeMax: z.string() },
    async ({ timeMin, timeMax }) => {
      const result = await findAvailability(timeMin, timeMax);
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );

  server.tool(
    "list_events",
    "List calendar events within a time range (ISO 8601 datetimes).",
    { timeMin: z.string(), timeMax: z.string() },
    async ({ timeMin, timeMax }) => {
      const result = await listEvents(timeMin, timeMax);
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );

  server.tool(
    "create_event",
    "Create a TENTATIVE calendar event on the user's own calendar. No invite email is sent to attendees — confirm via create_draft instead, subject to human approval.",
    {
      summary: z.string(),
      description: z.string().optional(),
      startIso: z.string().describe("ISO 8601 start datetime"),
      endIso: z.string().describe("ISO 8601 end datetime"),
      timeZone: z.string().describe("IANA timezone, e.g. 'America/New_York'"),
      attendeeEmails: z.array(z.string()).default([]),
    },
    async ({ summary, description, startIso, endIso, timeZone, attendeeEmails }) => {
      const result = await createTentativeEvent({
        summary,
        description,
        startIso,
        endIso,
        timeZone,
        attendeeEmails,
      });
      return { content: [{ type: "text", text: JSON.stringify(result) }] };
    }
  );
}
