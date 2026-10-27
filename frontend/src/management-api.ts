export class ManagementApiError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store' });
  const result = await response.json() as T & { detail?: { message?: string } };
  if (!response.ok) throw new ManagementApiError(result.detail?.message || 'Request failed', response.status);
  return result;
}

export async function mutateJson<T>(path: string, body: object, platform = false, method: 'POST' | 'PUT' = 'POST'): Promise<T> {
  const csrfPath = platform ? '/api/v1/platform/auth/csrf' : '/api/v1/auth/csrf';
  const csrf = await getJson<{ csrf_token: string }>(csrfPath);
  const response = await fetch(path, {
    method, credentials: 'same-origin', cache: 'no-store',
    headers: { 'content-type': 'application/json', 'x-csrf-token': csrf.csrf_token },
    body: JSON.stringify(body),
  });
  const result = await response.json() as T & { detail?: { message?: string } };
  if (!response.ok) throw new ManagementApiError(result.detail?.message || 'Request failed', response.status);
  return result;
}

async function csrfToken(): Promise<string> {
  return (await getJson<{ csrf_token: string }>('/api/v1/auth/csrf')).csrf_token;
}

export async function mutateForm<T>(path: string, body: FormData): Promise<T> {
  const response = await fetch(path, {
    method: 'POST', credentials: 'same-origin', cache: 'no-store',
    headers: { 'x-csrf-token': await csrfToken() }, body,
  });
  const result = await response.json() as T & { detail?: { message?: string } };
  if (!response.ok) throw new ManagementApiError(result.detail?.message || 'Request failed', response.status);
  return result;
}

export async function downloadFile(path: string): Promise<void> {
  const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store' });
  if (!response.ok) {
    let message = 'Download failed';
    try { message = ((await response.json()) as { detail?: { message?: string } }).detail?.message || message; } catch { /* non-JSON error */ }
    throw new ManagementApiError(message, response.status);
  }
  const blob = await response.blob();
  const disposition = response.headers.get('content-disposition') || '';
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || 'event-export.csv';
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = filename; link.click();
  URL.revokeObjectURL(url);
}
