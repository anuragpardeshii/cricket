export class ApiError extends Error { constructor(message: string, public status: number) { super(message); } }
let csrf = '';
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, { credentials: 'same-origin',
    method: body === undefined ? 'GET' : 'POST',
    headers: body === undefined ? {} : { 'Content-Type': 'application/json', 'X-Out-Request': '1', 'X-CSRF-Token': csrf },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({ detail: 'Service unavailable' }));
  if (!response.ok) {
    throw new ApiError(typeof data.detail === 'string' ? data.detail : 'Request failed', response.status);
  }
  if (data.csrf) csrf = data.csrf;
  return data as T;
}
export type Account = { user: { id: string; username: string; is_admin: boolean }; csrf: string };

export type BrowserSession = { user: Account['user'] | null; csrf: string; guest: boolean };
