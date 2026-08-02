import { getGmailAccessToken } from "./token-broker-client.js";

const CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3";

async function calendarFetch(path: string, init: RequestInit = {}): Promise<any> {
  // The token broker hands back a Gmail-scoped token; the same Google OAuth
  // grant also carries the calendar.events scope requested at connect time
  // (see GMAIL_SCOPES in the control plane's gmail provider), so it's valid
  // here too.
  const { access_token } = await getGmailAccessToken();
  const res = await fetch(`${CALENDAR_API_BASE}${path}`, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      Authorization: `Bearer ${access_token}`,
      "Content-Type": "application/json",
    },
  });
  if (!res.ok) {
    throw new Error(`Calendar API ${init.method ?? "GET"} ${path} failed: ${res.status} ${await res.text()}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export async function findAvailability(timeMin: string, timeMax: string) {
  return calendarFetch("/freeBusy", {
    method: "POST",
    body: JSON.stringify({ timeMin, timeMax, items: [{ id: "primary" }] }),
  });
}

export async function listEvents(timeMin: string, timeMax: string) {
  const params = new URLSearchParams({
    timeMin,
    timeMax,
    singleEvents: "true",
    orderBy: "startTime",
  });
  return calendarFetch(`/calendars/primary/events?${params.toString()}`);
}

/** Creates a **tentative** calendar event on the user's own calendar only.
 * `sendUpdates: "none"` means no invite email is dispatched to attendees —
 * confirming with the other party is the `draft-reply` skill's job, subject
 * to the same human-approval gate as every other outbound email. */
export async function createTentativeEvent(opts: {
  summary: string;
  description?: string;
  startIso: string;
  endIso: string;
  timeZone: string;
  attendeeEmails?: string[];
}) {
  const params = new URLSearchParams({ sendUpdates: "none" });
  return calendarFetch(`/calendars/primary/events?${params.toString()}`, {
    method: "POST",
    body: JSON.stringify({
      summary: opts.summary,
      description: opts.description,
      status: "tentative",
      start: { dateTime: opts.startIso, timeZone: opts.timeZone },
      end: { dateTime: opts.endIso, timeZone: opts.timeZone },
      attendees: (opts.attendeeEmails ?? []).map((email) => ({ email, responseStatus: "tentative" })),
    }),
  });
}
