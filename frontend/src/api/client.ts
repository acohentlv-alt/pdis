export async function apiFetch<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const msg = (body && typeof body === 'object' && typeof body.detail === 'string')
      ? body.detail
      : `API error: ${res.status}`;
    throw new Error(msg);
  }
  return res.json();
}
