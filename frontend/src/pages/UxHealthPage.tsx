// PRIVACY NOTE: This page is at /admin/ux-health — an unlisted URL.
// No auth — whole app is unauthed. Acceptable at n=2 users; anyone with the URL
// sees user-activity snapshots and stack traces. Revisit if user count grows.

import { useState, useEffect, useRef } from 'react';
import { apiFetch } from '../api/client';

interface UiEvent {
  id: number;
  event_name: string;
  severity: string;
  session_id: string;
  property_id: number | null;
  metadata: Record<string, unknown>;
  created_at_ilt: string;
}

interface RecentIssues {
  errors: UiEvent[];
  warnings: UiEvent[];
  summary: {
    page_views_24h: number;
    phone_reveals_24h: number;
    sessions_24h: number;
  };
}

function formatTime(ilt: string): string {
  // ILT comes as e.g. "2026-04-17 14:23:45.123456+03:00" — show date + time
  return ilt.replace('T', ' ').slice(0, 19);
}

function groupBySession(events: UiEvent[]): { session_id: string; events: UiEvent[] }[] {
  const map = new Map<string, UiEvent[]>();
  for (const e of events) {
    const group = map.get(e.session_id) ?? [];
    group.push(e);
    map.set(e.session_id, group);
  }
  return Array.from(map.entries()).map(([session_id, evts]) => ({ session_id, events: evts }));
}

function EventRow({ event }: { event: UiEvent }) {
  const [expanded, setExpanded] = useState(false);
  const meta = event.metadata;
  const oneLiner =
    (meta.message as string | undefined) ??
    (meta.response_snippet as string | undefined)?.slice(0, 80) ??
    event.event_name;

  return (
    <div
      className="border border-gray-200 rounded-lg overflow-hidden cursor-pointer"
      onClick={() => setExpanded(p => !p)}
    >
      <div className="flex items-start gap-3 px-3 py-2 bg-white hover:bg-gray-50 text-sm">
        <span className="text-gray-400 font-mono text-xs shrink-0 pt-0.5">{formatTime(event.created_at_ilt)}</span>
        <span className="font-medium text-gray-800 shrink-0">{event.event_name}</span>
        <span className="text-gray-500 truncate flex-1">{oneLiner}</span>
        <span className="text-gray-400 text-xs shrink-0">{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && (
        <div className="px-3 py-2 bg-gray-50 border-t border-gray-200">
          <pre className="text-xs text-gray-700 whitespace-pre-wrap break-all font-mono">
            {JSON.stringify(meta, null, 2)}
          </pre>
          <div className="text-xs text-gray-400 mt-1">session: {event.session_id} · property_id: {event.property_id ?? '—'}</div>
        </div>
      )}
    </div>
  );
}

function SessionGroup({ session_id, events }: { session_id: string; events: UiEvent[] }) {
  return (
    <div className="space-y-1">
      {events.length > 1 && (
        <div className="text-xs text-gray-500 font-medium px-1">
          {events.length} events in same session ({session_id.slice(0, 8)}…)
        </div>
      )}
      {events.map(e => <EventRow key={e.id} event={e} />)}
    </div>
  );
}

function Section({
  title,
  color,
  events,
  emptyMessage,
}: {
  title: string;
  color: 'red' | 'yellow' | 'green';
  events: UiEvent[];
  emptyMessage: string;
}) {
  const colorMap = {
    red: 'bg-red-50 border-red-200 text-red-800',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-800',
    green: 'bg-green-50 border-green-200 text-green-800',
  };
  const headerMap = {
    red: 'bg-red-100 border-red-200',
    yellow: 'bg-yellow-100 border-yellow-200',
    green: 'bg-green-100 border-green-200',
  };

  const groups = groupBySession(events);

  return (
    <div className={`rounded-xl border ${colorMap[color]} overflow-hidden`}>
      <div className={`px-4 py-2 border-b ${headerMap[color]} font-semibold text-sm`}>{title}</div>
      <div className="p-3 space-y-2">
        {events.length === 0 ? (
          <div className="text-sm text-center py-4">
            <span className="text-green-600 mr-1">✓</span> {emptyMessage}
          </div>
        ) : (
          groups.map(g => (
            <SessionGroup key={g.session_id} session_id={g.session_id} events={g.events} />
          ))
        )}
      </div>
    </div>
  );
}

export default function UxHealthPage() {
  // ALL hooks before any early return — React #310 rule
  const [data, setData] = useState<RecentIssues | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function load() {
    apiFetch<RecentIssues>('/api/ui-events/recent-issues?hours=168')
      .then(d => {
        setData(d);
        setLastRefresh(new Date());
        setError(null);
      })
      .catch(e => setError(String(e)));
  }

  useEffect(() => {
    load();
    intervalRef.current = setInterval(load, 30_000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  const summary = data?.summary;

  return (
    <div className="min-h-screen bg-gray-100 p-4">
      <div className="max-w-2xl mx-auto space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-gray-900">UX Health</h1>
          <span className="text-xs text-gray-400">
            {lastRefresh ? `Last refresh: ${lastRefresh.toLocaleTimeString()}` : 'Loading…'}
            {' · '}Auto-refresh 30s
          </span>
        </div>

        {error && (
          <div className="bg-red-100 border border-red-300 text-red-700 text-sm px-3 py-2 rounded-lg">
            Failed to load: {error}
          </div>
        )}

        {/* Green summary strip */}
        {summary && (
          <div className="bg-green-50 border border-green-200 rounded-xl px-4 py-3 text-sm text-green-800 font-medium">
            Last 24h: {summary.page_views_24h} page views · {summary.phone_reveals_24h} phone reveals · {summary.sessions_24h} sessions
          </div>
        )}

        {/* Red section — errors last 7 days */}
        <Section
          title="Errors (last 7 days)"
          color="red"
          events={data?.errors ?? []}
          emptyMessage="No issues detected."
        />

        {/* Yellow section — warnings last 7 days */}
        <Section
          title="Warnings (last 7 days)"
          color="yellow"
          events={data?.warnings ?? []}
          emptyMessage="No issues detected."
        />
      </div>
    </div>
  );
}
