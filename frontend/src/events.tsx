import { StrictMode, useEffect, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { Button, Dialog, Field, NavItem, Status, ThemeControl } from './ui';
import { getJson, ManagementApiError, mutateJson } from './management-api';
import { eventLocal, eventUtc } from './event-time';
import { describeEvent, type EventState } from './event-vocabulary';
import { TenantBrandMark } from './tenant-brand';
import { safeErrorMessage } from './safe-error';
import './event-management.css';

type FormField = { key: string; label: string; type: 'text' | 'textarea' | 'select' | 'checkbox'; required: boolean; options?: string[] };
type EventRecord = {
  id: string; slug: string; name: string; status: EventState; revision: number;
  description?: string | null; registration_mode?: 'public' | 'import_only';
  starts_at: string; ends_at: string; timezone: string; location: string | null;
  registration_opens_at: string | null; registration_closes_at: string | null;
  checkin_opens_at: string | null; checkin_closes_at: string | null;
  form_schema: { fields: FormField[] }; form_schema_version: number; pii_purge_due_at: string;
};
type Gate = { id: string; name: string; enabled: boolean };
type Panel = 'overview' | 'settings' | 'form' | 'gates' | 'readiness';
type Schedule = Pick<EventRecord, 'name' | 'location' | 'starts_at' | 'ends_at' | 'timezone' |
  'registration_opens_at' | 'registration_closes_at' | 'checkin_opens_at' | 'checkin_closes_at'>;
type EventDraft = Schedule & { description: string; registration_mode: 'public' | 'import_only' };
const emptySchedule: EventDraft = { name: '', location: '', description: '', registration_mode: 'import_only', starts_at: '', ends_at: '', timezone: 'Africa/Lagos',
  registration_opens_at: null, registration_closes_at: null, checkin_opens_at: null, checkin_closes_at: null };

function message(cause: unknown): string {
  if (cause instanceof ManagementApiError && cause.status === 409) return 'This event changed. Refresh it before trying again.';
  if (cause instanceof ManagementApiError && [401, 403].includes(cause.status)) return 'Your session or permission no longer allows this action. Sign in again if needed.';
  return safeErrorMessage(cause, 'The request could not be completed.');
}
function displayTime(instant: string | null, zone: string): string {
  return instant ? new Intl.DateTimeFormat('en-NG', { dateStyle: 'medium', timeStyle: 'short', timeZone: zone })
    .format(new Date(instant)) : 'Not set';
}
function DateField({ label: title, value, onChange, disabled = false, required = false }: {
  label: string; value: string | null; onChange: (value: string) => void; disabled?: boolean; required?: boolean;
}) {
  return <Field label={title} type="datetime-local" value={value ?? ''} disabled={disabled} required={required}
    onChange={(event) => onChange(event.target.value)}
    hint="Uses the event time zone. Skipped or repeated clock-change times need a different time." />;
}

function App() {
  const [events, setEvents] = useState<EventRecord[]>([]);
  const [selected, setSelected] = useState<EventRecord | null>(null);
  const [panel, setPanel] = useState<Panel>('overview');
  const [createMode, setCreateMode] = useState(false);
  const [schedule, setSchedule] = useState<EventDraft>(emptySchedule);
  const [fields, setFields] = useState<FormField[]>([]);
  const [gates, setGates] = useState<Gate[]>([]);
  const [gateName, setGateName] = useState('');
  const [editingGateId, setEditingGateId] = useState<string | null>(null);
  const [editingGateName, setEditingGateName] = useState('');
  const [readiness, setReadiness] = useState<string[]>([]);
  const [confirm, setConfirm] = useState<'publish' | 'close' | 'cancel' | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function refresh() {
    const list = await getJson<{ events: EventRecord[] }>('/api/v1/events');
    setEvents(list.events);
    if (selected) {
      const updated = list.events.find((row) => row.id === selected.id);
      if (updated) setSelected(updated);
    }
  }
  useEffect(() => { void getJson<{ events: EventRecord[] }>('/api/v1/events')
    .then((result) => {
      setEvents(result.events);
      const requestedId = new URLSearchParams(location.search).get('event');
      const requested = result.events.find((event) => event.id === requestedId);
      if (requested) choose(requested);
    }).catch((cause) => setError(message(cause)))
    .finally(() => setLoading(false)); }, []);
  useEffect(() => {
    if (!selected || panel !== 'readiness') return;
    void getJson<{ instructions: string[] }>(`/api/v1/events/${selected.id}/readiness`)
      .then((result) => setReadiness(result.instructions))
      .catch((cause) => setError(message(cause)));
  }, [selected?.id, panel]);
  function choose(event: EventRecord) {
    const local = (value: string | null) => value ? eventLocal(value, event.timezone) : null;
    setSelected(event); setSchedule({ name: event.name, location: event.location, description: event.description || '', registration_mode: event.registration_mode || 'public', starts_at: eventLocal(event.starts_at, event.timezone),
      ends_at: eventLocal(event.ends_at, event.timezone), timezone: event.timezone, registration_opens_at: local(event.registration_opens_at),
      registration_closes_at: local(event.registration_closes_at), checkin_opens_at: local(event.checkin_opens_at),
      checkin_closes_at: local(event.checkin_closes_at) });
    setFields(event.form_schema.fields); setPanel('overview'); setCreateMode(false); setError(''); setNotice('');
    history.replaceState(history.state, '', `${location.pathname}?event=${encodeURIComponent(event.id)}`);
    void Promise.all([
      getJson<{ gates: Gate[] }>(`/api/v1/events/${event.id}/gates`),
      getJson<{ instructions: string[] }>(`/api/v1/events/${event.id}/readiness`),
    ]).then(([gateResult, ready]) => { setGates(gateResult.gates); setReadiness(ready.instructions); })
      .catch((cause) => setError(message(cause)));
  }
  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try { await action(); }
    catch (cause) { setError(message(cause)); }
    finally { setBusy(false); }
  }
  function saveSchedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void run(async () => {
      const convert = (value: string | null) => value?.trim() ? eventUtc(value, schedule.timezone) : null;
      const prepared = selected?.status === 'published' ? {
        ...schedule,
        starts_at: selected.starts_at, ends_at: selected.ends_at,
        timezone: selected.timezone,
        registration_mode: selected.registration_mode || 'public',
        registration_opens_at: selected.registration_opens_at,
        registration_closes_at: selected.registration_closes_at,
        checkin_opens_at: selected.checkin_opens_at,
        checkin_closes_at: selected.checkin_closes_at,
      } : { ...schedule, starts_at: eventUtc(schedule.starts_at, schedule.timezone),
        ends_at: eventUtc(schedule.ends_at, schedule.timezone),
        registration_opens_at: convert(schedule.registration_opens_at),
        registration_closes_at: convert(schedule.registration_closes_at),
        checkin_opens_at: convert(schedule.checkin_opens_at),
        checkin_closes_at: convert(schedule.checkin_closes_at) };
      if (createMode) {
        const result = await mutateJson<EventRecord>('/api/v1/events', { ...prepared,
          registration_opens_at: undefined, registration_closes_at: undefined,
          checkin_opens_at: undefined, checkin_closes_at: undefined });
        await refresh(); choose(result); setNotice('Draft event created. Set its windows and gates before publishing.');
      } else if (selected) {
        const result = await mutateJson<EventRecord>(`/api/v1/events/${selected.id}`,
          { ...prepared,
            revision: selected.revision }, false, 'PUT');
        setSelected(result); await refresh(); setNotice('Event settings saved.');
      }
    });
  }
  function saveForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    void run(async () => {
      const result = await mutateJson<EventRecord>(`/api/v1/events/${selected.id}/form`,
        { revision: selected.revision, form_schema: { fields } }, false, 'PUT');
      setSelected(result); await refresh(); setNotice(`Form version ${result.form_schema_version} saved.`);
    });
  }
  function saveGate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    void run(async () => {
      await mutateJson(`/api/v1/events/${selected.id}/gates`, { name: gateName, enabled: true });
      const result = await getJson<{ gates: Gate[] }>(`/api/v1/events/${selected.id}/gates`);
      setGates(result.gates); setGateName(''); setNotice('Gate created.');
    });
  }
  function updateGate(gate: Gate) {
    if (!selected) return;
    void run(async () => {
      await mutateJson(`/api/v1/events/${selected.id}/gates/${gate.id}`,
        { name: gate.name, enabled: !gate.enabled }, false, 'PUT');
      const result = await getJson<{ gates: Gate[] }>(`/api/v1/events/${selected.id}/gates`);
      setGates(result.gates); setNotice(gate.enabled ? 'Gate disabled.' : 'Gate enabled.');
    });
  }
  function renameGate(event: FormEvent<HTMLFormElement>, gate: Gate) {
    event.preventDefault();
    if (!selected) return;
    void run(async () => {
      await mutateJson(`/api/v1/events/${selected.id}/gates/${gate.id}`,
        { name: editingGateName, enabled: gate.enabled }, false, 'PUT');
      const result = await getJson<{ gates: Gate[] }>(`/api/v1/events/${selected.id}/gates`);
      setGates(result.gates); setEditingGateId(null); setNotice('Gate renamed.');
    });
  }
  function transition(action: 'publish' | 'close' | 'cancel') {
    if (!selected) return;
    void run(async () => {
      const result = await mutateJson<EventRecord>(`/api/v1/events/${selected.id}/transitions/${action}`,
        { revision: selected.revision });
      setConfirm(null); setSelected(result); await refresh();
      setNotice(`Event ${describeEvent(result.status).title.toLowerCase()}.`);
    });
  }
  const editable = selected?.status === 'draft';
  return <main className="event-management">
    <header className="event-header"><div><p className="brand"><TenantBrandMark area="Events" /></p>
      <h1>{createMode ? 'Create event' : selected ? selected.name : 'Events'}</h1></div>
      <ThemeControl compact /></header>
    {error && <Status tone="danger" title="Action failed" instruction={error} announce="assertive" />}
    {notice && <Status tone="success" title="Updated" instruction={notice} announce="polite" />}
    {selected || createMode ? <div className="event-back"><Button variant="tertiary" onClick={() => {
      setSelected(null); setCreateMode(false); setPanel('overview'); setNotice(''); setError('');
      history.replaceState(history.state, '', location.pathname);
    }}>← All events</Button></div> : null}
    {!selected && !createMode && <section aria-label="Event overview">
      <div className="event-section-head"><div><h2>Your events</h2><p className="muted">Configure dates, registration and gates before publishing.</p></div>
        <Button onClick={() => { setCreateMode(true); setSchedule(emptySchedule); }}>Create event</Button></div>
      {loading ? <p role="status">Loading events…</p> : events.length === 0 ? <Status tone="info" title="No events yet"
        instruction="Create a draft event to begin configuration." /> : <div className="event-list">
        {events.map((row) => <div className="event-row" key={row.id}>
          <div><h3>{row.name}</h3><p className="muted">{displayTime(row.starts_at, row.timezone)} · {row.timezone}</p></div>
          <Status {...describeEvent(row.status)} />
          <Button variant="secondary" onClick={() => choose(row)}>Open event</Button>
        </div>)}</div>}</section>}
    {(createMode || selected) && <div className="event-content">
      {selected && <nav className="event-nav" aria-label="Event configuration">
        {(['overview', 'settings', 'form', 'gates', 'readiness'] as Panel[]).map((item) =>
          <NavItem key={item} href={`#${item}`} current={panel === item}
            onClick={(event) => { event.preventDefault(); setPanel(item); setError(''); setNotice(''); }}>
            {item[0].toUpperCase() + item.slice(1)}</NavItem>)}</nav>}
      {selected && panel === 'overview' && <section><h2>Event details</h2>
        <Status {...describeEvent(selected.status)} />
        <dl className="event-facts"><div><dt>Dates</dt><dd>{displayTime(selected.starts_at, selected.timezone)} to {displayTime(selected.ends_at, selected.timezone)}</dd></div>
          <div><dt>Time zone</dt><dd>{selected.timezone}</dd></div>
          <div><dt>Registration</dt><dd>{displayTime(selected.registration_opens_at, selected.timezone)} to {displayTime(selected.registration_closes_at, selected.timezone)}</dd></div>
          <div><dt>Check-in</dt><dd>{displayTime(selected.checkin_opens_at, selected.timezone)} to {displayTime(selected.checkin_closes_at, selected.timezone)}</dd></div>
          <div><dt>Personal-data purge due</dt><dd>{displayTime(selected.pii_purge_due_at, selected.timezone)}</dd></div></dl>
        <div className="event-actions">{selected.status === 'draft' && <Button onClick={() => setPanel('readiness')}>Review readiness</Button>}
          {selected.status === 'published' && <Button variant="secondary" onClick={() => setConfirm('close')}>Close event</Button>}
          {['draft', 'published'].includes(selected.status) && <Button variant="destructive" onClick={() => setConfirm('cancel')}>Cancel event</Button>}</div>
      </section>}
      {(createMode || panel === 'settings') && <section><h2>{createMode ? 'New event' : 'Event settings'}</h2>
        {selected && !editable && <p className="muted">Published dates and windows are fixed; only the name and location can change.</p>}
        <form className="event-form" onSubmit={saveSchedule}>
          <Field label="Event name" value={schedule.name} maxLength={160} required onChange={(event) => setSchedule({ ...schedule, name: event.target.value })} />
          <Field label="Location" value={schedule.location ?? ''} maxLength={300} onChange={(event) => setSchedule({ ...schedule, location: event.target.value })} />
          <label className="event-select-label">Registration mode<select value={schedule.registration_mode} disabled={!!selected && !editable} onChange={(event) => setSchedule({ ...schedule, registration_mode: event.target.value as EventDraft['registration_mode'] })}><option value="import_only">CSV import only</option><option value="public">Public self-registration</option></select></label>
          <label className="event-select-label">Description<textarea value={schedule.description} maxLength={2000} onChange={(event) => setSchedule({ ...schedule, description: event.target.value })} /></label>
          <Field label="IANA time zone" value={schedule.timezone} required hint="For example Africa/Lagos." onChange={(event) => setSchedule({ ...schedule, timezone: event.target.value })} disabled={!!selected && !editable} />
          <div className="event-field-grid">
            <DateField label="Event starts" value={schedule.starts_at} onChange={(value) => setSchedule({ ...schedule, starts_at: value })} disabled={!!selected && !editable} required />
            <DateField label="Event ends" value={schedule.ends_at} onChange={(value) => setSchedule({ ...schedule, ends_at: value })} disabled={!!selected && !editable} required />
          </div>
          {!createMode && <>{schedule.registration_mode === 'public' && <><h3>Registration window</h3><div className="event-field-grid">
            <DateField label="Registration opens" value={schedule.registration_opens_at} onChange={(value) => setSchedule({ ...schedule, registration_opens_at: value })} disabled={!editable} />
            <DateField label="Registration closes" value={schedule.registration_closes_at} onChange={(value) => setSchedule({ ...schedule, registration_closes_at: value })} disabled={!editable} />
          </div></>}<h3>Single check-in window</h3><div className="event-field-grid">
            <DateField label="Check-in opens" value={schedule.checkin_opens_at} onChange={(value) => setSchedule({ ...schedule, checkin_opens_at: value })} disabled={!editable} />
            <DateField label="Check-in closes" value={schedule.checkin_closes_at} onChange={(value) => setSchedule({ ...schedule, checkin_closes_at: value })} disabled={!editable} />
          </div></>}
          <Button type="submit" loading={busy}>{createMode ? 'Create draft' : 'Save settings'}</Button>
        </form></section>}
      {selected && panel === 'form' && <section><h2>Registration form</h2><p className="muted">Built-in name, email and phone fields are handled by registration. Add custom questions here. Version {selected.form_schema_version}.</p>
        {selected.status !== 'draft' ? <Status tone="warning" title="Form frozen" instruction="Published form versions cannot change." /> :
          <form className="event-form" onSubmit={saveForm}>
            {fields.map((field, index) => <fieldset className="event-fieldset" key={index}><legend>Question {index + 1}</legend>
              <Field label="Field key" value={field.key} required onChange={(event) => setFields(fields.map((row, i) => i === index ? { ...row, key: event.target.value } : row))} />
              <Field label="Question label" value={field.label} required onChange={(event) => setFields(fields.map((row, i) => i === index ? { ...row, label: event.target.value } : row))} />
              <label className="event-select-label">Answer type<select value={field.type} onChange={(event) => setFields(fields.map((row, i) => i === index ? { ...row, type: event.target.value as FormField['type'], options: event.target.value === 'select' ? ['Yes', 'No'] : undefined } : row))}>
                <option value="text">Short text</option><option value="textarea">Long text</option><option value="select">Choice</option><option value="checkbox">Checkbox</option></select></label>
              {field.type === 'select' && <Field label="Choices, separated by commas" value={(field.options ?? []).join(', ')} onChange={(event) => setFields(fields.map((row, i) => i === index ? { ...row, options: event.target.value.split(',').map((choice) => choice.trim()) } : row))} />}
              <label className="event-check"><input type="checkbox" checked={field.required} onChange={(event) => setFields(fields.map((row, i) => i === index ? { ...row, required: event.target.checked } : row))} /> Required answer</label>
              <Button variant="tertiary" onClick={() => setFields(fields.filter((_, i) => i !== index))}>Remove question {index + 1}</Button>
            </fieldset>)}
            <div className="event-actions"><Button variant="secondary" disabled={fields.length >= 30} onClick={() => setFields([...fields, { key: '', label: '', type: 'text', required: false }])}>Add question</Button>
              <Button type="submit" loading={busy}>Save new version</Button></div></form>}</section>}
      {selected && panel === 'gates' && <section><h2>Gates</h2><p className="muted">Enable a gate before publishing. Staff assignments stay within this event and gate.</p>
        {gates.length === 0 ? <Status tone="info" title="No gates" instruction="Create a gate to prepare check-in." /> :
          <div className="event-list">{gates.map((gate) => <div className="event-row" key={gate.id}><h3>{gate.name}</h3>
            <Status tone={gate.enabled ? 'success' : 'warning'} title={gate.enabled ? 'Enabled' : 'Disabled'} instruction={gate.enabled ? 'Available for assignment.' : 'Unavailable for check-in.'} />
            {['draft', 'published'].includes(selected.status) && <div className="event-actions">
              <Button variant="tertiary" onClick={() => { setEditingGateId(gate.id); setEditingGateName(gate.name); }}>Rename</Button>
              <Button variant="secondary" loading={busy} onClick={() => updateGate(gate)}>
                {gate.enabled ? 'Disable' : 'Enable'}</Button></div>}
            {editingGateId === gate.id && <form className="event-gate-form" onSubmit={(event) => renameGate(event, gate)}>
              <Field label={`New name for ${gate.name}`} value={editingGateName} required maxLength={80}
                onChange={(event) => setEditingGateName(event.target.value)} />
              <Button type="submit" loading={busy}>Save gate name</Button>
              <Button variant="tertiary" onClick={() => setEditingGateId(null)}>Cancel rename</Button>
            </form>}</div>)}</div>}
        {['draft', 'published'].includes(selected.status) && <form className="event-gate-form" onSubmit={saveGate}>
          <Field label="New gate name" value={gateName} required maxLength={80} onChange={(event) => setGateName(event.target.value)} />
          <Button type="submit" loading={busy}>Create gate</Button></form>}</section>}
      {selected && panel === 'readiness' && <section><h2>Publication readiness</h2>
        {readiness.length ? <Status tone="warning" title="Setup remaining" instruction={<ul>{readiness.map((item) => <li key={item}>{item}</li>)}</ul>} /> :
          <Status tone="success" title="Ready to publish" instruction="Dates, form and enabled gate are configured." />}
        <div className="event-actions"><Button variant="secondary" onClick={() => void run(async () => {
          const result = await getJson<{ instructions: string[] }>(`/api/v1/events/${selected.id}/readiness`);
          setReadiness(result.instructions);
        })}>Refresh readiness</Button>
          {selected.status === 'draft' && <Button disabled={readiness.length > 0} onClick={() => setConfirm('publish')}>Publish event</Button>}</div>
      </section>}
    </div>}
    <Dialog open={confirm !== null} onClose={() => setConfirm(null)} title={confirm === 'publish' ? 'Publish event?' : confirm === 'close' ? 'Close event?' : 'Cancel event?'}
      description={confirm === 'cancel' ? 'Cancellation is terminal. This event cannot reopen.' : confirm === 'close' ? 'Closing is final in v1.' : 'Review the configured dates, form and gates before publishing.'}>
      <div className="event-actions"><Button variant="secondary" onClick={() => setConfirm(null)}>Keep editing</Button>
        {confirm && <Button variant={confirm === 'cancel' ? 'destructive' : 'primary'} loading={busy} onClick={() => transition(confirm)}>
          Confirm {confirm}</Button>}</div></Dialog>
  </main>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
