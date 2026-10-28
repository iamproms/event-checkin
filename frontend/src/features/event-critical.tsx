import { useCallback, useEffect, useMemo, useState } from 'react';
import { eventApi, type Attendance, type EventSummary, type Gate, type ImportJob, type ImportPreview, type Participant } from '../event-api';
import { getJson, mutateJson } from '../management-api';
import { ButtonLink, DataTable, EmptyState, ErrorState, FilterBar, MetricStrip, PageHeader, SectionHeader, StatusMark } from '../product/components';
import { Icon } from '../product/icons';
import { useEventWorkspace } from '../product/EventWorkspaceContext';
import { safeErrorMessage } from '../safe-error';
import { Dialog, Progress } from '../ui';
import { routeHref } from '../product/router';

function message(error: unknown) { return safeErrorMessage(error); }
function date(value?: string | null) { return value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—'; }
function humanize(value: string) { return value.replaceAll('_', ' ').replace(/^./, letter => letter.toUpperCase()); }
const importIssueLabels: Record<string, string> = {
  DUPLICATE_EMAIL_IN_FILE: 'Email appears more than once in this file.',
  DUPLICATE_PHONE_IN_FILE: 'Phone number appears more than once in this file.',
  EMAIL_ALREADY_REGISTERED: 'Email is already registered for this event.',
  PHONE_ALREADY_REGISTERED: 'Phone number is already registered for this event.',
  INVALID_EMAIL: 'Enter a valid email address.',
  INVALID_PHONE: 'Enter a valid phone number.',
  REQUIRED: 'A required value is missing.',
};
function readableImportIssue(value: string) { return importIssueLabels[value] || 'This row contains a value that could not be accepted.'; }

export function useEvents() {
  return useEventWorkspace();
}

export function EventPicker({ events, value, onChange }: { events: EventSummary[]; value: string; onChange: (value: string) => void }) {
  return <label className="event-picker"><span>Event</span><select value={value} disabled={!events.length} onChange={event => onChange(event.target.value)}>{!events.length && <option value="">No events available</option>}{events.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>;
}

export function OrganizerOverview() {
  const { events, loading, error, reload, selectedEvent, selectedEventId, setSelectedEventId } = useEventWorkspace();
  const [attendance, setAttendance] = useState<Attendance | null>(null);
  const [attendanceLoading, setAttendanceLoading] = useState(false);
  const [attendanceError, setAttendanceError] = useState('');
  const loadAttendance = useCallback(async () => {
    if (!selectedEventId || selectedEvent?.status !== 'published') { setAttendance(null); return; }
    setAttendanceLoading(true); setAttendanceError('');
    try { setAttendance(await eventApi.attendance(selectedEventId)); }
    catch (cause) { setAttendanceError(message(cause)); }
    finally { setAttendanceLoading(false); }
  }, [selectedEventId, selectedEvent?.status]);
  useEffect(() => { void loadAttendance(); }, [loadAttendance]);
  const visibleAttendance = attendance?.event_id === selectedEventId ? attendance : null;

  return <><PageHeader eyebrow={selectedEvent?.name || 'Organizer workspace'} title="Overview" description="The current event, its readiness, and the next operational actions." actions={<ButtonLink href="/events.html">Create event <Icon name="plus" /></ButtonLink>} />
    {loading ? <section className="panel-section"><DataTable label="Loading events" columns={['Event','Lifecycle','Schedule']} rows={[]} loading /></section> : error ? <ErrorState title="Events unavailable" description={error} onRetry={() => void reload()} /> : !events.length ? <EmptyState icon="events" title="Create your first event" description="Set the schedule, registration mode, check-in window, and gates before inviting participants." action={<ButtonLink href="/events.html">Create event</ButtonLink>} /> : <>
      <div className="toolbar-row"><EventPicker events={events} value={selectedEventId} onChange={setSelectedEventId}/>{selectedEvent && <StatusMark tone={selectedEvent.status === 'published' ? 'success' : selectedEvent.status === 'cancelled' ? 'danger' : 'neutral'}>{selectedEvent.status}</StatusMark>}</div>
      {selectedEvent?.status === 'published' ? attendanceError ? <ErrorState title="Attendance unavailable" description={attendanceError} onRetry={() => void loadAttendance()} /> : <>
        <MetricStrip metrics={[{ label: 'Registered', value: attendanceLoading ? '…' : String(visibleAttendance?.registered ?? 0), detail: 'Authoritative records' }, { label: 'Checked in', value: attendanceLoading ? '…' : String(visibleAttendance?.checked_in ?? 0), detail: 'Server-confirmed' }, { label: 'Remaining', value: attendanceLoading ? '…' : String(visibleAttendance?.remaining ?? 0), detail: 'Not yet admitted' }, { label: 'Attendance', value: attendanceLoading ? '…' : `${(visibleAttendance?.attendance_percent ?? 0).toFixed(1)}%`, detail: visibleAttendance ? `Updated ${date(visibleAttendance.refreshed_at)}` : 'Loading current totals' }]} />
        <div className="content-grid"><section className="panel-section"><SectionHeader title="Next actions" description="Continue with the selected event"/><div className="task-list"><a href={routeHref('participants')}><span><strong>{visibleAttendance?.registered ? 'Review participants' : 'Add participants'}</strong><small>{visibleAttendance?.registered ? `${visibleAttendance.registered} registrations are available.` : 'Import a CSV or open public registration.'}</small></span><Icon name="arrow" /></a><a href={routeHref('tickets')}><span><strong>Prepare tickets</strong><small>Issue credentials, review delivery, and retry failures.</small></span><Icon name="arrow" /></a><a href={routeHref('check-in')}><span><strong>Open live attendance</strong><small>Monitor server-confirmed admissions by gate.</small></span><Icon name="arrow" /></a></div></section><aside className="panel-section"><SectionHeader title="Event context"/><dl className="fact-list"><div><dt>Schedule</dt><dd>{date(selectedEvent.starts_at)} to {date(selectedEvent.ends_at)}</dd></div><div><dt>Location</dt><dd>{selectedEvent.location || 'Not set'}</dd></div><div><dt>Registration</dt><dd>{selectedEvent.registration_mode === 'import_only' ? 'CSV import only' : 'Public and imported'}</dd></div></dl><ButtonLink href={`/events.html?event=${encodeURIComponent(selectedEvent.id)}`} secondary>Configure event</ButtonLink></aside></div>
      </> : <section className="panel-section"><SectionHeader title="Event preparation" description={`${selectedEvent?.name || 'This event'} is ${selectedEvent?.status || 'not available for check-in'}.`} /><div className="task-list"><a href="/events.html"><span><strong>Review event configuration</strong><small>Complete schedule, registration, gates, and publication readiness.</small></span><Icon name="arrow" /></a><a href={routeHref('participants')}><span><strong>Prepare participants</strong><small>Review the directory and import requirements.</small></span><Icon name="arrow" /></a></div></section>}
    </>}
  </>;
}

export function LiveEventsDirectory() {
  const { events, loading, error, reload } = useEvents(); const [query, setQuery] = useState(''); const [status, setStatus] = useState('all');
  const filtered = useMemo(() => events.filter(event => (status === 'all' || event.status === status) && `${event.name} ${event.slug}`.toLowerCase().includes(query.toLowerCase())), [events, query, status]);
  return <><PageHeader eyebrow="Organizer workspace" title="Events" description="Create, configure and publish the authoritative event experience." actions={<ButtonLink href="/events.html">Create event <Icon name="plus" /></ButtonLink>} />
    <div className="live-callout"><StatusMark tone="success">Live event records</StatusMark><p>Schedule, registration form, check-in window, gates and lifecycle remain managed through the secure event editor.</p></div>
    <FilterBar placeholder="Search events" count={loading ? 'Loading…' : `${filtered.length} events`} value={query} onChange={setQuery}><select aria-label="Filter lifecycle" value={status} onChange={event => setStatus(event.target.value)}><option value="all">All lifecycles</option><option value="draft">Draft</option><option value="published">Published</option><option value="closed">Closed</option><option value="cancelled">Cancelled</option></select><button className="icon-button" aria-label="Refresh events" onClick={() => void reload()}><Icon name="operations" /></button></FilterBar>
    {error ? <ErrorState title="Events unavailable" description={error} onRetry={() => void reload()} /> : loading ? <DataTable label="Events" columns={['Event','Schedule','Location','Lifecycle','Action']} rows={[]} loading /> : filtered.length ? <DataTable label="Events" columns={['Event','Schedule','Location','Lifecycle','Action']} rows={filtered.map(event => [<span>{event.name}<br/><small>{event.slug}</small></span>,`${date(event.starts_at)} to ${date(event.ends_at)}`,event.location || 'Not set',<StatusMark tone={event.status === 'published' ? 'success' : event.status === 'cancelled' ? 'danger' : 'neutral'}>{humanize(event.status)}</StatusMark>,<ButtonLink secondary href={`/events.html?event=${encodeURIComponent(event.id)}`}>Configure</ButtonLink>])} /> : <EmptyState icon="events" title="No events found" description="Adjust the search or create an event in the live configuration workflow." action={<ButtonLink href="/events.html">Create event</ButtonLink>} />}
  </>;
}

type ImportStage = 'choose' | 'mapping' | 'validated' | 'processing' | 'committed' | 'failed';
const importFields = [{ key: 'full_name', label: 'Full name', required: false }, { key: 'email', label: 'Email address', required: true }, { key: 'phone', label: 'Phone number', required: false }] as const;

function ImportWorkflow({ event, onCommitted }: { event: EventSummary | undefined; onCommitted: () => void }) {
  const eventId = event?.id || '';
  const [stage, setStage] = useState<ImportStage>('choose'); const [preview, setPreview] = useState<ImportPreview | null>(null); const [job, setJob] = useState<ImportJob | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({}); const [customMapping, setCustomMapping] = useState<Record<string, string>>({});
  const [policy, setPolicy] = useState<{ available: boolean; message: string } | null>(null);
  const [policyLoading, setPolicyLoading] = useState(false);
  const [authorizationConfirmed, setAuthorizationConfirmed] = useState(false);
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const columns = preview?.columns || preview?.headers || []; const importId = preview?.import_id || preview?.id || '';
  const fullMapping = { ...mapping, custom: customMapping };
  useEffect(() => { setStage('choose'); setPreview(null); setJob(null); setPolicy(null); setAuthorizationConfirmed(false); setError(''); }, [eventId]);
  useEffect(() => {
    if (stage !== 'mapping' || !eventId) return;
    let active = true;
    setPolicyLoading(true);
    void eventApi.importPolicy(eventId).then(value => { if (active) setPolicy(value); })
      .catch(cause => { if (active) setPolicy({ available: false, message: message(cause) }); })
      .finally(() => { if (active) setPolicyLoading(false); });
    return () => { active = false; };
  }, [eventId, stage]);
  useEffect(() => {
    if (stage !== 'processing' || !eventId || !importId) return;
    let active = true;
    const check = async () => {
      try {
        const next = await eventApi.importStatus(eventId, importId);
        if (!active) return;
        setJob(next); setError('');
        if (next.status === 'completed') { setStage('committed'); onCommitted(); }
        else if (next.status === 'failed') { setStage('failed'); setError('The import job failed. Download the row errors and upload a corrected file.'); }
      } catch (cause) { if (active) setError(message(cause)); }
    };
    void check(); const timer = setInterval(() => void check(), 1500);
    return () => { active = false; clearInterval(timer); };
  }, [eventId, importId, stage]);
  async function upload(file?: File) { if (!file || !eventId) return; setBusy(true); setError(''); setAuthorizationConfirmed(false); try { const next = await eventApi.previewImport(eventId, file); const source = next.columns || next.headers || []; setPreview(next); setMapping(next.suggested_mapping || { full_name: source.find(column => /full.?name|name/i.test(column)) || '', email: source.find(column => /e.?mail/i.test(column)) || '', phone: source.find(column => /phone|mobile|tel/i.test(column)) || '' }); if (next.reused && ['queued','processing','completed','failed'].includes(next.status || '')) { setJob(next); setStage(next.status === 'completed' ? 'committed' : next.status === 'failed' ? 'failed' : 'processing'); } else setStage('mapping'); } catch (cause) { setError(message(cause)); } finally { setBusy(false); } }
  async function validate() { setBusy(true); setError(''); setAuthorizationConfirmed(false); try { const result = await eventApi.validateImport(eventId, importId, fullMapping); setJob(result); setStage('validated'); } catch (cause) { setError(message(cause)); } finally { setBusy(false); } }
  async function commit() {
    setBusy(true); setError('');
    try {
      const result = await eventApi.commitImport(eventId, importId, authorizationConfirmed); setJob(result);
      if (result.status === 'completed') { setStage('committed'); onCommitted(); return; }
      if (result.status === 'failed') { setStage('failed'); throw new Error('The import job failed. Download the row errors and correct the source file.'); }
      setStage('processing');
    } catch (cause) { setError(message(cause)); } finally { setBusy(false); }
  }
  async function downloadErrors() { setError(''); try { await eventApi.importErrors(eventId, importId); } catch (cause) { setError(message(cause)); } }
  const requiredCustomMissing = (event?.form_schema?.fields || []).some(field => field.required && !customMapping[field.key]);
  const validationBlocker = !mapping.email ? 'Map the email address column to continue.'
    : requiredCustomMissing ? 'Map every required event question to a source column.'
    : policyLoading || !policy ? 'Checking the organization privacy notice…'
    : !policy.available ? policy.message : '';
  return <section className="panel-section import-workflow" aria-labelledby="import-title"><SectionHeader title="Bulk participant import" description="CSV or XLSX · preview, map, validate, then commit" />
    <ol className="stepper" aria-label="Import progress">{['Choose file','Map columns','Validate','Confirm and import'].map((label,index) => { const current = stage === 'processing' ? 3 : ['choose','mapping','validated','committed'].indexOf(stage); return <li key={label} className={index <= current ? 'is-complete' : ''}>{label}</li>; })}</ol>
    {stage === 'choose' && <div className="upload-zone"><Icon name="attendees"/><h3 id="import-title">Choose an attendee file</h3><p>The file is uploaded to the tenant-scoped import service. Accepted formats: .csv and .xlsx.</p><label className="product-button">{busy ? 'Uploading…' : 'Choose CSV or XLSX'}<input className="sr-only" type="file" accept=".csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv" disabled={busy || !eventId} onChange={event => void upload(event.target.files?.[0])}/></label></div>}
    {stage === 'mapping' && <><div className="mapping-grid">{importFields.map(field => <label key={field.key}><span>{field.label}{field.required ? ' *' : ''}</span><select value={mapping[field.key] || ''} onChange={event => setMapping(current => ({ ...current, [field.key]: event.target.value }))}><option value="">{field.required ? 'Select source column' : 'Not provided'}</option>{columns.map(column => <option key={column} value={column}>{column}</option>)}</select></label>)}{(event?.form_schema?.fields || []).map(field => <label key={field.key}><span>{field.label}{field.required ? ' *' : ''}</span><select value={customMapping[field.key] || ''} onChange={change => setCustomMapping(current => ({...current, [field.key]: change.target.value}))}><option value="">{field.required ? 'Select source column' : 'Not provided'}</option>{columns.map(column => <option key={column} value={column}>{column}</option>)}</select></label>)}</div>
      <p className={policy && !policy.available && !policyLoading ? 'request-error' : 'live-callout'} role="status">{policyLoading ? 'Checking the approved privacy notice…' : policy?.message || 'Checking the approved privacy notice…'}</p>
      <div className="preview-summary"><span>{preview?.row_count || preview?.total_rows || 0} rows detected</span><span>{columns.length} columns</span><span>No records created yet</span></div>
      {preview?.sample?.length ? <DataTable label="Import preview, first eight rows" columns={columns.slice(0,6)} rows={preview.sample.map(row => columns.slice(0,6).map(column => row[column] || '—'))}/> : null}
      <div className="page-actions"><button className="product-button product-button--secondary" onClick={() => { setPreview(null); setStage('choose'); }}>Choose another file</button><button className="product-button" disabled={busy || !!validationBlocker} aria-busy={busy} onClick={() => void validate()}>{busy ? <><span className="gate-spinner" aria-hidden="true"/> Validating rows…</> : 'Validate rows'}</button></div>{validationBlocker && validationBlocker !== policy?.message && <p className="form-help" role="status">{validationBlocker}</p>}</>}
    {(stage === 'validated' || stage === 'processing' || stage === 'committed' || stage === 'failed') && <><MetricStrip metrics={[{label:'Rows',value:String(job?.row_count ?? 0),detail:'Uploaded'},{label:'Valid',value:String(job?.valid_count ?? 0),detail:'Eligible to create'},{label:'Invalid',value:String(job?.invalid_count ?? 0),detail:'Requires correction'},{label:'Duplicates',value:String(job?.duplicate_count ?? 0),detail:'Not overwritten'}]} />
      {job?.errors?.length ? <DataTable label="Import validation errors" columns={['Row','Issues']} rows={job.errors.slice(0,10).map(row => [row.row_number,row.errors.map(readableImportIssue).join('; ')])}/> : null}
      {stage === 'validated' && <label className="import-authorization"><input type="checkbox" checked={authorizationConfirmed} onChange={change => setAuthorizationConfirmed(change.target.checked)}/><span>I confirm that I have the appropriate authority and lawful basis to process these attendee records for event check-in and transactional ticket communications.</span></label>}
      <div className="page-actions"><button className="product-button product-button--secondary" onClick={() => { setPreview(null); setJob(null); setAuthorizationConfirmed(false); setStage('choose'); }}>Upload corrected file</button><button className="product-button product-button--secondary" onClick={() => void downloadErrors()}>Download row errors</button>{stage === 'validated' && <button className="product-button" disabled={busy || (job?.valid_count ?? 0) < 1 || !authorizationConfirmed} onClick={() => void commit()}>{busy ? 'Starting import…' : 'Import attendees'}</button>}</div>
      {stage === 'validated' && !authorizationConfirmed && <p className="form-help" role="status">Confirm your authority and lawful basis before importing attendees.</p>}
      {stage === 'processing' && <div className="processing-banner" role="status"><div><strong>Import processing</strong><p>Registrations are being committed in the background. You can keep this page open to see completion.</p><Progress label="Participant import" value={job?.progress ?? 0} /></div></div>}
      {stage === 'committed' && <div className="success-banner" role="status"><Icon name="checkin"/><div><strong>Import completed</strong><p>{job?.imported_count ?? 0} registrations were created. {event?.registration_mode === 'import_only' ? 'Review the results, then issue tickets from Ticketing.' : 'Ticket issuance has been queued.'}</p></div></div>}</>}
    {error && <p className="request-error" role="alert">{error}</p>}
  </section>;
}

export function ParticipantsWorkspace() {
  const { events, loading: eventsLoading, selectedEventId: activeEvent, setSelectedEventId } = useEvents();
  const [participants, setParticipants] = useState<Participant[]>([]); const [query, setQuery] = useState(''); const [cursor, setCursor] = useState(0); const [nextCursor, setNextCursor] = useState<string | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [tab, setTab] = useState<'directory'|'import'>('directory');
  const load = useCallback(async (offset = cursor) => { if (!activeEvent) return; setBusy(true); setError(''); try { const result = await eventApi.participants(activeEvent, query, offset); setParticipants(result.registrations); setNextCursor(result.next_cursor); setCursor(offset); } catch (cause) { setError(message(cause)); } finally { setBusy(false); } }, [activeEvent, query, cursor]);
  useEffect(() => { setParticipants([]); if (activeEvent) void load(0); }, [activeEvent]);
  const selectedEvent = events.find(event => event.id === activeEvent);
  return <><PageHeader eyebrow={selectedEvent?.name || 'Event operations'} title="Participants" description="One authoritative directory for public and imported registrations." actions={<button className="product-button" onClick={() => setTab('import')} disabled={!activeEvent}>Import participants</button>} />
    <div className="toolbar-row"><EventPicker events={events} value={activeEvent} onChange={setSelectedEventId}/><div className="tabs" role="tablist"><button role="tab" aria-selected={tab === 'directory'} onClick={() => setTab('directory')}>Directory</button><button role="tab" aria-selected={tab === 'import'} onClick={() => setTab('import')}>Bulk import</button></div></div>
    {tab === 'directory' ? <><FilterBar placeholder="Search email, phone or registration" value={query} onChange={setQuery} count={busy ? 'Loading…' : `${participants.length} registrations`}><button className="product-button product-button--secondary" disabled={busy || !activeEvent} onClick={() => void load()}>Search</button></FilterBar>
      {error ? <ErrorState title="Participants unavailable" description={error} onRetry={() => void load(0)} /> : participants.length || busy ? <><DataTable label="Event registrations" columns={['Participant','Phone','Source','Registration','Ticket','Registered','Support']} loading={busy && !participants.length} rows={participants.map(item => [<span>{item.full_name || item.email}<br/>{item.full_name && <small>{item.email}</small>}</span>,item.phone || 'Not provided',humanize(item.source),<StatusMark tone={item.status === 'registered' ? 'success' : 'neutral'}>{humanize(item.status)}</StatusMark>,<StatusMark tone={item.ticket_status === 'active' && ['sent','delivered'].includes(item.delivery_status || '') ? 'success' : item.delivery_status === 'failed' ? 'danger' : 'warning'}>{humanize(item.delivery_status || item.ticket_status || 'pending')}</StatusMark>,date(item.registered_at),<a className="section-link" href={routeHref('tickets', { event: activeEvent, registration: item.id })}>Manage ticket</a>])}/><div className="page-actions"><button className="product-button product-button--secondary" disabled={busy || cursor === 0} onClick={() => void load(Math.max(0,cursor-50))}>Previous</button><button className="product-button product-button--secondary" disabled={busy || !nextCursor} onClick={() => void load(Number(nextCursor))}>Next</button></div></> : !eventsLoading && <EmptyState icon="attendees" title="No registrations found" description={query ? 'No participant matches this search. Clear it or try an email address.' : 'Import participants or open public registration for this event.'} action={!query && <button className="product-button" onClick={() => setTab('import')}>Import participants</button>} />}</> : <ImportWorkflow event={events.find(item => item.id === activeEvent)} onCommitted={() => void load(0)}/>}
  </>;
}

export function AttendanceDashboard({ exportOnly = false }: { exportOnly?: boolean }) {
  const { events, selectedEvent, selectedEventId: activeEvent, setSelectedEventId } = useEvents(); const [attendance, setAttendance] = useState<Attendance | null>(null); const [busy, setBusy] = useState(false); const [exporting, setExporting] = useState(false); const [exported, setExported] = useState(false); const [error, setError] = useState('');
  const load = useCallback(async () => { if (!activeEvent) return; setBusy(true); setError(''); try { setAttendance(await eventApi.attendance(activeEvent)); } catch (cause) { setError(message(cause)); } finally { setBusy(false); } }, [activeEvent]);
  useEffect(() => { setAttendance(null); if (activeEvent) void load(); }, [activeEvent, load]);
  useEffect(() => { if (!activeEvent || exportOnly) return; const timer = setInterval(() => void load(), 15000); return () => clearInterval(timer); }, [activeEvent, exportOnly, load]);
  async function exportCsv() { if (!activeEvent) return; setExporting(true); setExported(false); setError(''); try { await eventApi.exportAttendance(activeEvent); setExported(true); } catch (cause) { setError(message(cause)); } finally { setExporting(false); } }
  const visibleAttendance = attendance?.event_id === activeEvent ? attendance : null;
  const maxGate = Math.max(...(visibleAttendance?.gates.map(gate => gate.checked_in) || []), 1);
  return <><PageHeader eyebrow={selectedEvent?.name || 'Event operations'} title={exportOnly ? 'Attendance export' : 'Live attendance'} description={exportOnly ? 'Download authorized participant-level attendance for the selected event.' : 'Server-confirmed admissions with a 15-second operational refresh.'} actions={<><button className="product-button product-button--secondary" onClick={() => void load()} disabled={busy || !activeEvent}>{busy ? 'Refreshing…' : 'Refresh'}</button><button className="product-button" onClick={() => void exportCsv()} disabled={!activeEvent || exporting}>{exporting ? 'Preparing CSV…' : 'Export CSV'}</button></>} />
    <div className="toolbar-row"><EventPicker events={events} value={activeEvent} onChange={setSelectedEventId}/>{visibleAttendance && <StatusMark tone="success">Confirmed {date(visibleAttendance.refreshed_at)}</StatusMark>}</div>
    {error && <ErrorState title={exporting ? 'Export unavailable' : 'Attendance unavailable'} description={error} onRetry={!exporting ? () => void load() : undefined} />}
    {exported && <div className="success-banner" role="status"><Icon name="checkin"/><div><strong>CSV download started</strong><p>The export is scoped to {selectedEvent?.name || 'the selected event'} and the signed-in role.</p></div></div>}
    {visibleAttendance ? <><MetricStrip metrics={[{label:'Registered',value:String(visibleAttendance.registered),detail:'Authoritative records'},{label:'Checked in',value:String(visibleAttendance.checked_in),detail:'Confirmed redemptions'},{label:'Remaining',value:String(visibleAttendance.remaining),detail:'Not yet admitted'},{label:'Attendance',value:`${visibleAttendance.attendance_percent.toFixed(1)}%`,detail:`${visibleAttendance.duplicate_scans} duplicate · ${visibleAttendance.invalid_scans} invalid`}]} />
      {!exportOnly && <div className="content-grid"><section className="panel-section"><SectionHeader title="Gate throughput" description="Confirmed check-ins by assigned gate"/>{visibleAttendance.gates.length ? <div className="bar-list">{visibleAttendance.gates.map(gate => <div className="bar-row" key={gate.gate_id}><span>{gate.gate_name}</span><div className="bar-track" aria-hidden="true"><div className="bar-fill" style={{width:`${Math.max(2, (gate.checked_in / maxGate) * 100)}%`}} /></div><strong>{gate.checked_in}</strong></div>)}</div> : <p className="quiet-empty">No gate activity has been confirmed yet.</p>}</section><section className="panel-section"><SectionHeader title="Recent activity" description="No participant identity is shown"/><DataTable label="Recent check-ins" columns={['Time','Gate','Outcome']} emptyMessage="Confirmed scans will appear here." rows={visibleAttendance.recent.map(item => [date(item.occurred_at),item.gate_name,<StatusMark tone={item.outcome === 'accepted' ? 'success' : item.outcome === 'duplicate' ? 'warning' : 'danger'}>{humanize(item.outcome)}</StatusMark>])}/></section></div>}
      {exportOnly && <section className="panel-section export-note"><Icon name="shield"/><div><h2>Privacy-scoped export</h2><p>The server applies event scope and role authorization. The CSV contains only the participant fields permitted to the signed-in operator and should be handled under the event retention policy.</p></div></section>}</> : busy ? <section className="panel-section"><DataTable label="Loading attendance" columns={['Metric','Current value']} rows={[]} loading /></section> : <EmptyState icon="checkin" title={activeEvent ? 'Attendance has not loaded' : 'Choose an event'} description="Attendance is never inferred locally. Metrics appear only after a successful server response." />}
  </>;
}

export function GateStaffWorkspace() {
  const { events, selectedEventId: activeEvent, setSelectedEventId } = useEvents();
  const [gates, setGates] = useState<Gate[]>([]); const [gatesLoading, setGatesLoading] = useState(false); const [gateId, setGateId] = useState(''); const [email, setEmail] = useState(''); const [role, setRole] = useState<'gate_supervisor'|'gate_scanner'>('gate_scanner'); const [busy, setBusy] = useState(false); const [notice, setNotice] = useState(''); const [error, setError] = useState('');
  type Staff = { user_id: string; email: string; role: string; status: string; assignments: Array<{ event_id: string; gate_id: string }> };
  const [staff, setStaff] = useState<Staff[]>([]);
  const [staffLoading, setStaffLoading] = useState(false);
  const [staffError, setStaffError] = useState('');
  const [confirmation, setConfirmation] = useState<{ member: Staff; action: 'move' | 'revoke' } | null>(null);
  const refreshStaff = useCallback(async () => {
    setStaffLoading(true);
    try { setStaff((await getJson<{ staff: Staff[] }>('/api/v1/auth/gate-staff')).staff); setStaffError(''); }
    catch (cause) { setStaffError(message(cause)); }
    finally { setStaffLoading(false); }
  }, []);
  useEffect(() => { void refreshStaff(); }, [refreshStaff]);
  useEffect(() => {
    setGates([]); setGateId(''); setError('');
    if (!activeEvent) return;
    setGatesLoading(true);
    void eventApi.gates(activeEvent).then(rows => { const enabled = rows.filter(gate => gate.enabled); setGates(enabled); setGateId(enabled[0]?.id || ''); })
      .catch(cause => setError(message(cause))).finally(() => setGatesLoading(false));
  }, [activeEvent]);
  async function invite() { if (!activeEvent || !gateId || !email) return; setBusy(true); setError(''); setNotice(''); try { await eventApi.inviteGateStaff(email, role, activeEvent, gateId); setNotice(`Invitation requested for ${email}. Delivery is handled by the configured transactional mail service; inspect Mailpit locally.`); setEmail(''); await refreshStaff(); } catch (cause) { setError(message(cause)); } finally { setBusy(false); } }
  async function staffAction(member: Staff, action: 'move' | 'revoke') {
    if (action === 'move' && (!activeEvent || !gateId)) return;
    setBusy(true); setError(''); setNotice('');
    try {
      await mutateJson(`/api/v1/auth/memberships/${member.user_id}/${action === 'move' ? 'gate-assignment' : 'revoke'}`, action === 'move' ? { event_id: activeEvent, gate_id: gateId } : {});
      setNotice(action === 'move' ? 'Assignment changed. The staff member must sign in again.' : 'Gate staff access revoked.');
      await refreshStaff();
    } catch (cause) { setError(message(cause)); } finally { setBusy(false); }
  }
  async function confirmStaffAction() {
    if (!confirmation) return;
    const pending = confirmation; setConfirmation(null);
    await staffAction(pending.member, pending.action);
  }
  const selectedEvent = events.find(event => event.id === activeEvent);
  const selectedGate = gates.find(gate => gate.id === gateId);
  return <><PageHeader eyebrow="Access control" title="Gate staff" description="Invite staff into an event-and-gate scoped role without broadening tenant access." actions={<ButtonLink href="/gate.html">Open scanner</ButtonLink>} />
    <div className="content-grid" style={{marginTop:22}}><section className="panel-section"><SectionHeader title="Invite assigned staff" description="The invitation link is delivered by the configured email transport."/><div className="form-grid form-grid--single"><EventPicker events={events} value={activeEvent} onChange={setSelectedEventId}/><label>Gate<select value={gateId} disabled={gatesLoading || !gates.length} onChange={event => setGateId(event.target.value)}>{gatesLoading ? <option value="">Loading gates…</option> : !gates.length ? <option value="">No enabled gates</option> : gates.map(gate => <option key={gate.id} value={gate.id}>{gate.name}</option>)}</select></label><label>Role<select value={role} onChange={event => setRole(event.target.value as 'gate_supervisor'|'gate_scanner')}><option value="gate_scanner">Gate scanner</option><option value="gate_supervisor">Gate supervisor</option></select></label><label>Email address<input type="email" value={email} onChange={event => setEmail(event.target.value)} autoComplete="email"/></label></div><button className="product-button" aria-busy={busy || undefined} aria-describedby={!gatesLoading && !gateId ? 'gate-invite-reason' : undefined} disabled={busy || !email || !gateId} onClick={() => void invite()}>{busy ? 'Sending invitation…' : 'Send gate invitation'}</button>{!gatesLoading && activeEvent && !gateId && <p className="control-note" id="gate-invite-reason">Create or enable a gate in {selectedEvent?.name || 'the selected event'} before inviting gate staff.</p>}{notice && <div className="success-banner" role="status"><Icon name="checkin"/><div><strong>Invitation requested</strong><p>{notice}</p></div></div>}{error && <ErrorState title="Gate assignment unavailable" description={error} />}</section>
      <aside className="panel-section"><SectionHeader title="Role boundaries"/><DataTable label="Gate role boundaries" columns={['Role','Access','MFA']} rows={[[<strong>Gate scanner</strong>,'Assigned event and gate scanner only','Scoped policy exception'],[<strong>Gate supervisor</strong>,'Assigned event and gate operations','Required']]}/><div className="live-callout"><Icon name="shield"/><p>Invitations do not create active accounts. The recipient must accept the delivered link, set a password and complete required MFA before access is granted.</p></div></aside></div>
    <section className="panel-section"><SectionHeader title="Gate staff directory" description="Move active staff to the event and gate selected above, or revoke their tenant access." />
      {staffError ? <ErrorState title="Gate staff unavailable" description={staffError} onRetry={() => void refreshStaff()} /> : <DataTable label="Authorized gate staff" loading={staffLoading} emptyMessage="No gate staff have been invited yet." columns={['Staff','Role','Assignment','Status','Actions']} rows={staff.map(member => [member.email,humanize(member.role),member.assignments.map(item => `${events.find(event => event.id === item.event_id)?.name || 'Unknown event'} · ${gates.find(gate => gate.id === item.gate_id)?.name || 'Assigned gate'}`).join(', ') || 'No active assignment',<StatusMark tone={member.status === 'active' ? 'success' : 'warning'}>{humanize(member.status)}</StatusMark>,<div className="page-actions" key={member.user_id}><button className="product-button product-button--secondary" disabled={busy || member.status !== 'active' || !activeEvent || !gateId} onClick={() => setConfirmation({ member, action:'move' })}>Move</button><button className="product-button product-button--secondary" disabled={busy || member.status !== 'active'} onClick={() => setConfirmation({ member, action:'revoke' })}>Revoke</button></div>])} />}
      <button className="product-button product-button--secondary" aria-busy={staffLoading || undefined} disabled={staffLoading} onClick={() => void refreshStaff()}>{staffLoading ? 'Refreshing staff…' : 'Refresh staff'}</button>
    </section>
    <Dialog open={!!confirmation} onClose={() => setConfirmation(null)} title={confirmation?.action === 'revoke' ? 'Revoke gate access?' : 'Move gate assignment?'} description={confirmation?.action === 'revoke' ? `${confirmation.member.email} will lose gate access immediately.` : `${confirmation?.member.email || 'This staff member'} will move to ${selectedEvent?.name || 'the selected event'} at ${selectedGate?.name || 'the selected gate'}. Their current session will end.`}><div className="dialog-actions"><button className="product-button product-button--secondary" onClick={() => setConfirmation(null)}>Cancel</button><button className="product-button" onClick={() => void confirmStaffAction()}>{confirmation?.action === 'revoke' ? 'Revoke access' : 'Move assignment'}</button></div></Dialog>
  </>;
}
