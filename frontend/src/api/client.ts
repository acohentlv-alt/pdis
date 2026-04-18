import { logEvent } from '../lib/telemetry';

export async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  // Skip telemetry for the telemetry endpoint itself to prevent infinite loops
  const isTelemetry = url.includes('/api/ui-events');

  const method = options?.method ?? 'GET';
  const path = url;
  const start = performance.now();

  let res: Response;
  try {
    res = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options?.headers },
      ...options,
    });
  } catch (err) {
    // Network failure — fetch itself threw
    if (!isTelemetry) {
      logEvent('api_error', { path, method, status: 0, message: String(err) }, {}, 'error');
    }
    throw err;
  }

  const duration_ms = Math.round(performance.now() - start);

  if (!isTelemetry && duration_ms > 3000) {
    logEvent('slow_response', { path, method, duration_ms }, {}, 'warn');
  }

  if (!res.ok) {
    let response_snippet: string | null = null;
    let errMsg: string;
    try {
      const text = await res.text();
      response_snippet = text.slice(0, 500);
      const body = JSON.parse(text);
      errMsg = (body && typeof body === 'object' && typeof body.detail === 'string')
        ? body.detail
        : `API error: ${res.status}`;
    } catch {
      errMsg = `API error: ${res.status}`;
    }
    if (!isTelemetry) {
      logEvent('api_error', { path, method, status: res.status, response_snippet }, {}, 'error');
    }
    throw new Error(errMsg);
  }

  return res.json();
}
