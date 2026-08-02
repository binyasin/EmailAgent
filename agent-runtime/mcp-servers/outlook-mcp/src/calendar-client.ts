import { getOutlookAccessToken } from "./token-broker-client.js";

const GRAPH_API_BASE = "https://graph.microsoft.com/v1.0";

async function graphFetch(path: string, init: RequestInit = {}): Promise<any> {
  const { access_token } = await getOutlookAccessToken();
  const res = await fetch(`${GRAPH_API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      Authorization: `Bearer ${access_token}`,
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) {
    throw new Error(`Graph API ${init.method ?? "GET"} ${path} failed: ${res.status} ${await res.text()}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export async function findAvailability(schedules: string[], startIso: string, endIso: string) {
  return graphFetch("/me/calendar/getSchedule", {
    method: "POST",
    body: JSON.stringify({
      schedules,
      startTime: { dateTime: startIso, timeZone: "UTC" },
      endTime: { dateTime: endIso, timeZone: "UTC" },
      availabilityViewInterval: 30,
    }),
  });
}

export async function listEvents(startIso: string, endIso: string) {
  const params = new URLSearchParams({ startDateTime: startIso, endDateTime: endIso });
  return graphFetch(`/me/calendarView?${params.toString()}`);
}

/** Creates a **tentative** calendar event. `showAs: "tentative"` and no
 * meeting invite is sent (this is a plain event, not an Outlook "meeting"
 * with attendee invites) — confirming with the other party is the
 * `draft-reply` skill's job, subject to the same human-approval gate as
 * every other outbound email. */
export async function createTentativeEvent(opts: {
  subject: string;
  bodyText?: string;
  startIso: string;
  endIso: string;
  timeZone: string;
}) {
  return graphFetch("/me/events", {
    method: "POST",
    body: JSON.stringify({
      subject: opts.subject,
      body: { contentType: "text", content: opts.bodyText ?? "" },
      start: { dateTime: opts.startIso, timeZone: opts.timeZone },
      end: { dateTime: opts.endIso, timeZone: opts.timeZone },
      showAs: "tentative",
      isReminderOn: false,
    }),
  });
}
