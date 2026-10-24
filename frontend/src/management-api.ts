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
