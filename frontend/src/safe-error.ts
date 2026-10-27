import { ManagementApiError } from './management-api';

export function safeErrorMessage(error: unknown, fallback = 'The request could not be completed.') {
  if (error instanceof ManagementApiError) return error.message;
  if (error instanceof TypeError) return 'The service could not be reached. Check the connection and try again.';
  return fallback;
}

export function safeMessageForStatus(status: number, fallback = 'The request could not be completed.') {
  if (status === 400 || status === 422) return 'Some information could not be accepted. Review the fields and try again.';
  if (status === 401) return 'Your session is no longer authorized. Sign in and try again.';
  if (status === 403) return 'Your account does not have permission for this action.';
  if (status === 404) return 'The requested record could not be found. It may have changed or been removed.';
  if (status === 409) return 'This information changed before the action completed. Refresh and try again.';
  if (status === 413) return 'The selected file is too large.';
  if (status === 429) return 'Too many attempts were made. Wait a moment before trying again.';
  if (status >= 500) return 'The service is temporarily unavailable. Try again shortly.';
  return fallback;
}
