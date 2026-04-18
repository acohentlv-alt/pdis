// PRIVACY NOTE: This module is used by /admin/ux-health — an unlisted URL.
// No auth — whole app is unauthed. Acceptable at n=2 users; anyone with the URL
// sees user-activity snapshots and stack traces. Revisit if user count grows.

// IMPORTANT: logEvent uses raw fetch, NOT apiFetch.
// apiFetch is instrumented to call logEvent on api_errors. If logEvent went
// through apiFetch, a failing POST to /api/ui-events would trigger another
// logEvent → infinite loop. Keep this using raw fetch only.

const SESSION_KEY = 'pdis_session_id';

function getSessionId(): string {
  let id = sessionStorage.getItem(SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    sessionStorage.setItem(SESSION_KEY, id);
  }
  return id;
}

type LogEventOpts = {
  yad2_id?: string;
  property_id?: number;
};

export function logEvent(
  event_name: string,
  metadata: Record<string, unknown> = {},
  opts: LogEventOpts = {},
  severity: 'info' | 'warn' | 'error' = 'info'
): void {
  const body = {
    event_name,
    severity,
    session_id: getSessionId(),
    yad2_id: opts.yad2_id ?? null,
    property_id: opts.property_id ?? null,
    metadata,
  };
  fetch('/api/ui-events', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).catch(() => { /* fire-and-forget; network drops acceptable */ });
}
