export class ManagementApiError extends Error {
  constructor(message: string, readonly status: number) { super(message); }
}

function errorMessage(status: number) {
  if (status === 400 || status === 422) return 'Some information could not be accepted. Review it and try again.';
  if (status === 401) return 'Your session is no longer authorized. Sign in and try again.';
  if (status === 403) return 'Your account does not have permission for this action.';
  if (status === 404) return 'The requested record could not be found. It may have changed or been removed.';
  if (status === 409) return 'This information changed before the action completed. Refresh and try again.';
  if (status === 413) return 'The selected file is too large.';
  if (status === 429) return 'Too many attempts were made. Wait a moment before trying again.';
  if (status >= 500) return 'The service is temporarily unavailable. Try again shortly.';
  return 'The request could not be completed.';
}

function approvedDetailMessage(result: unknown, status: number) {
  if (!result || typeof result !== 'object') return errorMessage(status);
  const detail = (result as { detail?: unknown }).detail;
  if (!detail || typeof detail !== 'object') return errorMessage(status);
  const code = (detail as { code?: unknown }).code;
  const message = (detail as { message?: unknown }).message;
  if (code === 'BRANDING_INVALID' && typeof message === 'string' && message.length <= 400 && !/[{}<>]/.test(message)) return message;
  if (code === 'EVENT_CONFLICT') return 'This record changed in another session. Refresh it before saving again.';
  return errorMessage(status);
}

async function jsonResponse<T>(response: Response): Promise<T> {
  let result: T;
  try { result = await response.json() as T; }
  catch { throw new ManagementApiError(response.ok ? 'The service returned an unreadable response.' : errorMessage(response.status), response.status); }
  if (!response.ok) throw new ManagementApiError(approvedDetailMessage(result, response.status), response.status);
  return result;
}

export async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store' });
  return jsonResponse<T>(response);
}

export async function mutateJson<T>(path: string, body: object, platform = false, method: 'POST' | 'PUT' = 'POST'): Promise<T> {
  const csrfPath = platform ? '/api/v1/platform/auth/csrf' : '/api/v1/auth/csrf';
  const csrf = await getJson<{ csrf_token: string }>(csrfPath);
  const response = await fetch(path, {
    method, credentials: 'same-origin', cache: 'no-store',
    headers: { 'content-type': 'application/json', 'x-csrf-token': csrf.csrf_token },
    body: JSON.stringify(body),
  });
  return jsonResponse<T>(response);
}

async function csrfToken(): Promise<string> {
  return (await getJson<{ csrf_token: string }>('/api/v1/auth/csrf')).csrf_token;
}

export async function mutateForm<T>(path: string, body: FormData): Promise<T> {
  const response = await fetch(path, {
    method: 'POST', credentials: 'same-origin', cache: 'no-store',
    headers: { 'x-csrf-token': await csrfToken() }, body,
  });
  return jsonResponse<T>(response);
}

export async function downloadFile(path: string): Promise<void> {
  const response = await fetch(path, { credentials: 'same-origin', cache: 'no-store' });
  if (!response.ok) {
    throw new ManagementApiError(errorMessage(response.status), response.status);
  }
  const blob = await response.blob();
  const disposition = response.headers.get('content-disposition') || '';
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1] || 'event-export.csv';
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url; link.download = filename; link.click();
  URL.revokeObjectURL(url);
}
