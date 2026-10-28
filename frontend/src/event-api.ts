import { downloadFile, getJson, mutateForm, mutateJson } from './management-api';

export type EventSummary = {
  id: string; slug: string; name: string; status: string; starts_at: string; ends_at: string;
  location?: string | null; registration_mode?: 'public' | 'import_only'; revision: number;
  form_schema?: { fields: { key: string; label: string; required: boolean }[] };
};

export type Participant = {
  id: string; full_name: string; email: string; phone?: string | null; status: string; source: string;
  registered_at: string; ticket_status?: string | null; delivery_status?: string | null;
};

export type ImportRow = {
  row: number; email?: string | null; phone?: string | null; status: 'valid' | 'invalid' | 'duplicate';
  errors?: string[];
};

export type ImportPreview = {
  id?: string; import_id?: string; filename?: string; headers?: string[]; columns?: string[];
  suggested_mapping?: Record<string, string>; rows?: ImportRow[]; sample?: Record<string, string>[];
  row_count?: number; total_rows?: number; valid_count?: number; invalid_count?: number;
  duplicate_count?: number; imported_count?: number; errors?: { row_number: number; errors: string[] }[];
  status?: string;
  reused?: boolean;
};

export type ImportJob = ImportPreview & {
  progress?: number; committed_at?: string | null;
};

export type Attendance = {
  event_id: string; registered: number; checked_in: number; remaining: number;
  attendance_percent: number; duplicate_scans: number; invalid_scans: number; refreshed_at: string;
  gates: { gate_id: string; gate_name: string; checked_in: number }[];
  recent: { occurred_at: string; gate_name: string; outcome: string }[];
};

export type GateSession = {
  authenticated?: boolean; role?: string; event_id?: string; event_name?: string; gate_id?: string; gate_name?: string;
  assignments?: { event_id: string; event_name: string; gate_id: string; gate_name: string; event_status?: string }[];
};
export type Gate = { id: string; event_id: string; name: string; enabled: boolean };

export type RedemptionResult = {
  outcome: 'accepted' | 'duplicate' | 'revoked' | 'invalid';
  reason_code: 'ACCEPTED' | 'DUPLICATE_ADMISSION' | 'REVOKED_TICKET' | 'INVALID_TICKET' |
    'EVENT_UNAVAILABLE' | 'GATE_UNAVAILABLE' | 'CHECKIN_NOT_OPEN' | 'CHECKIN_CLOSED' |
    'CHECKIN_WINDOW_UNAVAILABLE';
  confirmed_at: string;
};

export const eventApi = {
  events: async () => (await getJson<{ events: EventSummary[] }>('/api/v1/events')).events,
  gates: async (eventId: string) => (await getJson<{ gates: Gate[] }>(`/api/v1/events/${encodeURIComponent(eventId)}/gates`)).gates,
  participants: (eventId: string, query = '', cursor = 0) => getJson<{ registrations: Participant[]; next_cursor: string | null }>(`/api/v1/events/${encodeURIComponent(eventId)}/registrations?q=${encodeURIComponent(query)}&cursor=${cursor}`),
  previewImport: async (eventId: string, file: File) => {
    const body = new FormData(); body.append('file', file);
    return mutateForm<ImportPreview>(`/api/v1/events/${encodeURIComponent(eventId)}/imports/preview`, body);
  },
  importPolicy: (eventId: string) => getJson<{ available: boolean; message: string }>(
    `/api/v1/events/${encodeURIComponent(eventId)}/imports/policy`,
  ),
  validateImport: (eventId: string, importId: string, mapping: Record<string, unknown>) => mutateJson<ImportJob>(
    `/api/v1/events/${encodeURIComponent(eventId)}/imports/${encodeURIComponent(importId)}/validate`,
    { mapping },
  ),
  commitImport: (eventId: string, importId: string, authorizationConfirmed: boolean) => mutateJson<ImportJob>(
    `/api/v1/events/${encodeURIComponent(eventId)}/imports/${encodeURIComponent(importId)}/commit`,
    { authorization_confirmed: authorizationConfirmed },
  ),
  importStatus: (eventId: string, importId: string) => getJson<ImportJob>(`/api/v1/events/${encodeURIComponent(eventId)}/imports/${encodeURIComponent(importId)}`),
  importErrors: (eventId: string, importId: string) => downloadFile(`/api/v1/events/${encodeURIComponent(eventId)}/imports/${encodeURIComponent(importId)}/errors.csv`),
  attendance: (eventId: string) => getJson<Attendance>(`/api/v1/events/${encodeURIComponent(eventId)}/attendance`),
  exportAttendance: (eventId: string) => downloadFile(`/api/v1/events/${encodeURIComponent(eventId)}/attendance/export.csv`),
  gateSession: () => getJson<GateSession>('/api/v1/gate/session'),
  inviteGateStaff: (email: string, role: 'gate_supervisor' | 'gate_scanner', eventId: string, gateId: string) => mutateJson<{ state: string }>('/api/v1/auth/invitations', { email, role, event_id: eventId, gate_id: gateId }),
  redeem: (eventId: string, gateId: string, credential: string) => mutateJson<RedemptionResult>('/api/v1/gate/redeem', { event_id: eventId, gate_id: gateId, credential }),
};
