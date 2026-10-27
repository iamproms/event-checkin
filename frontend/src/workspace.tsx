import { StrictMode, useEffect, useState, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { AppShell, type NavItem } from './product/AppShell';
import { capabilities } from './product/capabilities';
import { ButtonLink, CapabilityNotice, DataTable, EmptyState, ErrorState, FilterBar, MetricStrip, PageHeader, SectionHeader, SettingRow, StatusMark } from './product/components';
import { routeHref, useHashRoute } from './product/router';
import { EventWorkspaceProvider, useEventWorkspace } from './product/EventWorkspaceContext';
import { getJson, mutateJson } from './management-api';
import { AttendanceDashboard, EventPicker, GateStaffWorkspace, LiveEventsDirectory, OrganizerOverview, ParticipantsWorkspace, useEvents } from './features/event-critical';
import { eventApi, type Participant } from './event-api';
import { Dialog } from './ui';
import { safeErrorMessage } from './safe-error';
import './product/product.css';

const nav: NavItem[] = [
  { route: 'dashboard', label: 'Dashboard', icon: 'overview' }, { route: 'events', label: 'Events', icon: 'events' },
  { route: 'participants', label: 'Participants', icon: 'attendees' }, { route: 'tickets', label: 'Tickets', icon: 'tickets' },
  { route: 'check-in', label: 'Check-in', icon: 'checkin' }, { route: 'gate-staff', label: 'Gate staff', icon: 'team' },
  { route: 'communications', label: 'Communications', icon: 'messages', badge: 'Soon' }, { route: 'reports', label: 'Reports', icon: 'reports' },
  { route: 'branding', label: 'Branding', icon: 'organizations' }, { route: 'settings', label: 'Settings', icon: 'settings' },
];

function Dashboard() {
  return <OrganizerOverview />;
}

const Events = LiveEventsDirectory;
const Attendees = ParticipantsWorkspace;

type TicketState = { ticket_status: string; delivery_status: string; delivery_error?: string | null };
type BulkTicketState = { registered: number; issued: number; queued: number; sent: number; delivered: number; failed: number };
function humanize(value: string) { return value.replaceAll('_', ' ').replace(/^./, letter => letter.toUpperCase()); }
function Tickets() {
  const params = new URLSearchParams(location.hash.split('?')[1] || '');
  const { events, selectedEventId: activeBulkEvent, setSelectedEventId } = useEvents();
  const bulkEvent = events.find(item => item.id === activeBulkEvent);
  const [bulkState, setBulkState] = useState<BulkTicketState | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkError, setBulkError] = useState('');
  const [bulkNotice, setBulkNotice] = useState('');
  const [showEmailPreview, setShowEmailPreview] = useState(false);
  const [participants, setParticipants] = useState<Participant[]>([]); const [participantsLoading, setParticipantsLoading] = useState(false); const [participantsError, setParticipantsError] = useState(''); const [query, setQuery] = useState('');
  const [registrationId, setRegistrationId] = useState(params.get('registration') || '');
  const [ticket, setTicket] = useState<TicketState | null>(null); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const [confirmation, setConfirmation] = useState<{ action: 'issue'|'send'|'resend'|'reissue'|'revoke'; title: string; description: string } | null>(null);
  const eventId = activeBulkEvent;
  const path = `/api/v1/events/${encodeURIComponent(eventId)}/registrations/${encodeURIComponent(registrationId)}/ticket`;
  async function load() { if (!eventId || !registrationId) return; setBusy(true); setError(''); try { setTicket(await getJson<TicketState>(path)); } catch (cause) { setTicket(null); setError(safeErrorMessage(cause, 'Ticket state could not be loaded.')); } finally { setBusy(false); } }
  async function command(action: 'resend'|'reissue'|'revoke') { setBusy(true); setError(''); try { setTicket(await mutateJson<TicketState>(`${path}/${action}`, {})); await Promise.all([refreshBulk(), refreshParticipants()]); } catch (cause) { setError(safeErrorMessage(cause, 'The ticket action could not be completed.')); } finally { setBusy(false); } }
  async function refreshBulk() { if (!activeBulkEvent) return; setBulkBusy(true); setBulkError(''); try { setBulkState(await getJson<BulkTicketState>(`/api/v1/events/${encodeURIComponent(activeBulkEvent)}/tickets/bulk`)); } catch (cause) { setBulkError(safeErrorMessage(cause, 'Ticket totals could not be loaded.')); } finally { setBulkBusy(false); } }
  async function refreshParticipants() { if (!activeBulkEvent) return; setParticipantsLoading(true); setParticipantsError(''); try { setParticipants((await eventApi.participants(activeBulkEvent, '', 0)).registrations); } catch (cause) { setParticipantsError(safeErrorMessage(cause, 'Participants could not be loaded.')); } finally { setParticipantsLoading(false); } }
  useEffect(() => { setBulkState(null); if (activeBulkEvent) void refreshBulk(); }, [activeBulkEvent]);
  useEffect(() => { setParticipants([]); setTicket(null); if (activeBulkEvent) void refreshParticipants(); }, [activeBulkEvent]);
  useEffect(() => { if (activeBulkEvent && registrationId) void load(); }, [activeBulkEvent, registrationId]);
  async function bulkCommand(action: 'issue' | 'send') {
    if (!activeBulkEvent) return;
    setBulkBusy(true); setBulkError(''); setBulkNotice('');
    try { const result = await mutateJson<Record<string, number>>(`/api/v1/events/${encodeURIComponent(activeBulkEvent)}/tickets/bulk/${action}`, {}); setBulkNotice(action === 'issue' ? `${result.queued_or_existing ?? 0} eligible registrations are queued or already issued.` : `${result.newly_queued ?? 0} new messages queued. “Sent” means provider acceptance, not inbox delivery.`); setBulkState(await getJson<BulkTicketState>(`/api/v1/events/${encodeURIComponent(activeBulkEvent)}/tickets/bulk`)); }
    catch (cause) { setBulkError(safeErrorMessage(cause, 'The bulk action could not be completed.')); }
    finally { setBulkBusy(false); }
  }
  function selectParticipant(participant: Participant) {
    setRegistrationId(participant.id); setTicket(null); setError('');
    history.replaceState(history.state, '', routeHref('tickets', { event: activeBulkEvent, registration: participant.id }));
  }
  function selectTicketEvent(eventId: string) {
    setRegistrationId(''); setTicket(null); setError(''); setQuery(''); setSelectedEventId(eventId);
    history.replaceState(history.state, '', routeHref('tickets', { event: eventId, registration: null }));
  }
  async function confirmAction() {
    if (!confirmation) return;
    const action = confirmation.action; setConfirmation(null);
    if (action === 'issue' || action === 'send') await bulkCommand(action);
    else await command(action);
  }
  const selectedParticipant = participants.find(participant => participant.id === registrationId);
  const filteredParticipants = participants.filter(participant => `${participant.full_name} ${participant.email}`.toLowerCase().includes(query.toLowerCase()));
  return <><PageHeader eyebrow={bulkEvent?.name || 'Event operations'} title="Tickets" description="Issue credentials, review delivery, and resolve ticket problems." /><CapabilityNotice capability={capabilities.tickets}>Ticket state and actions are server-authoritative. QR credentials are never returned to this workspace.</CapabilityNotice>
    <section className="panel-section"><SectionHeader title="Imported attendee tickets" description="Issue first, review the message, then queue email separately." />
      <div className="toolbar-row"><EventPicker events={events} value={activeBulkEvent} onChange={selectTicketEvent}/><button className="product-button product-button--secondary" aria-busy={bulkBusy || undefined} disabled={bulkBusy || !activeBulkEvent} onClick={() => void refreshBulk()}>{bulkBusy ? 'Refreshing…' : 'Refresh progress'}</button></div>
      {bulkState ? <MetricStrip metrics={[{label:'Registrations',value:String(bulkState.registered),detail:'Imported records'},{label:'Issued',value:String(bulkState.issued),detail:'Active credentials'},{label:'Email queued',value:String(bulkState.queued),detail:'Waiting for provider'},{label:'Delivery issues',value:String(bulkState.failed),detail:`${bulkState.sent} accepted · ${bulkState.delivered} delivered`}]} /> : <DataTable label="Loading ticket totals" columns={['Registrations','Issued','Queued','Delivery']} rows={[]} loading={bulkBusy} emptyMessage="Ticket totals are unavailable." />}
      <div className="page-actions"><button className="product-button" aria-busy={bulkBusy || undefined} disabled={bulkBusy || !activeBulkEvent || bulkEvent?.status !== 'published'} aria-describedby={bulkEvent && bulkEvent.status !== 'published' ? 'ticket-issue-reason' : undefined} onClick={() => setConfirmation({action:'issue',title:'Issue QR tickets?',description:`Create secure credentials for eligible registrations in ${bulkEvent?.name || 'this event'}. Existing tickets remain unchanged.`})}>Issue QR tickets</button><button className="product-button product-button--secondary" disabled={!activeBulkEvent} onClick={() => setShowEmailPreview(value => !value)}>{showEmailPreview ? 'Hide email preview' : 'Preview ticket email'}</button><button className="product-button" aria-busy={bulkBusy || undefined} disabled={bulkBusy || !activeBulkEvent || !bulkState?.issued} aria-describedby={bulkState && !bulkState.issued ? 'ticket-email-reason' : undefined} onClick={() => setConfirmation({action:'send',title:'Queue ticket emails?',description:'Queue transactional email for issued imported tickets without a prior send. Provider acceptance does not prove inbox delivery.'})}>Queue ticket emails</button></div>
      {bulkEvent && bulkEvent.status !== 'published' && <p className="control-note" id="ticket-issue-reason">Publish this event before issuing QR tickets.</p>}
      {bulkState && !bulkState.issued && <p className="control-note" id="ticket-email-reason">Issue at least one ticket before queueing ticket email.</p>}
      {showEmailPreview && <div className="ticket-email-preview"><p><strong>Preview only · no recipient or credential</strong></p><h3>Your ticket for {bulkEvent?.name || 'the event'}</h3><p>{bulkEvent?.starts_at ? new Date(bulkEvent.starts_at).toLocaleString() : 'Event date'} · {bulkEvent?.location || 'Venue to be confirmed'}</p><p>Present your unique QR code at the gate. Keep it private; the first valid scan uses it.</p><p>For ticket help, contact the event organizer.</p><p>The delivery worker inserts each attendee’s unique QR image. This preview does not send email.</p></div>}
      {bulkNotice && <p className="success-banner" role="status">{bulkNotice}</p>}{bulkError && <ErrorState title="Ticket operation unavailable" description={bulkError} onRetry={() => void refreshBulk()} />}
    </section>
    <section className="panel-section"><SectionHeader title="Participant tickets" description="Choose a participant to inspect current ticket and delivery state."/><FilterBar placeholder="Search participant or email" value={query} onChange={setQuery} count={participantsLoading ? 'Loading…' : `${filteredParticipants.length} participants`}><button className="product-button product-button--secondary" onClick={() => void refreshParticipants()} disabled={participantsLoading || !activeBulkEvent}>Refresh</button></FilterBar>{participantsError ? <ErrorState title="Participants unavailable" description={participantsError} onRetry={() => void refreshParticipants()} /> : <DataTable label="Participant tickets" loading={participantsLoading && !participants.length} emptyMessage={query ? 'No participant matches this search.' : 'Participants will appear after registration or import.'} columns={['Participant','Ticket','Delivery','Action']} rows={filteredParticipants.map(participant => [<span>{participant.full_name || participant.email}<br/>{participant.full_name && <small>{participant.email}</small>}</span>,<StatusMark tone={participant.ticket_status === 'active' ? 'success' : 'warning'}>{humanize(participant.ticket_status || 'not issued')}</StatusMark>,<StatusMark tone={['sent','delivered'].includes(participant.delivery_status || '') ? 'success' : participant.delivery_status === 'failed' ? 'danger' : 'warning'}>{humanize(participant.delivery_status || 'not queued')}</StatusMark>,<button className="product-button product-button--secondary" onClick={() => selectParticipant(participant)}>Manage</button>])}/>}</section>
    {error && <ErrorState title="Ticket unavailable" description={error} onRetry={registrationId ? () => void load() : undefined} />}
    {ticket ? <section className="panel-section"><SectionHeader title={selectedParticipant ? `${selectedParticipant.full_name || selectedParticipant.email}'s ticket` : 'Authoritative ticket state'} description="The credential itself is never returned."/><DataTable label="Ticket state" columns={['Ticket','Delivery','Delivery detail']} rows={[[<StatusMark tone={ticket.ticket_status==='active'?'success':'danger'}>{humanize(ticket.ticket_status)}</StatusMark>,<StatusMark tone={ticket.delivery_status==='sent'||ticket.delivery_status==='delivered'?'success':ticket.delivery_status==='failed'?'danger':'warning'}>{humanize(ticket.delivery_status)}</StatusMark>,ticket.delivery_error ? 'The delivery provider reported a failure.' : 'No provider error reported']]} /><div className="page-actions" style={{marginTop:16}}><button className="product-button product-button--secondary" disabled={busy} onClick={() => setConfirmation({action:'resend',title:'Resend this ticket?',description:'Keep the active credential and create an idempotent delivery request.'})}>Resend</button><button className="product-button product-button--secondary" disabled={busy} onClick={() => setConfirmation({action:'reissue',title:'Reissue this ticket?',description:'Revoke the current credential, create a replacement, and queue new delivery.'})}>Reissue</button><button className="product-button" disabled={busy || ticket.ticket_status!=='active'} onClick={() => setConfirmation({action:'revoke',title:'Revoke this ticket?',description:'The current credential will stop working immediately. No replacement is issued.'})}>Revoke</button></div><details className="support-details"><summary>Support identifiers</summary><dl><div><dt>Event ID</dt><dd><code>{eventId}</code></dd></div><div><dt>Registration ID</dt><dd><code>{registrationId}</code></dd></div></dl></details></section> : busy && registrationId ? <section className="panel-section"><DataTable label="Loading ticket state" columns={['Ticket','Delivery','Delivery detail']} rows={[]} loading /></section> : <EmptyState icon="tickets" title="Choose a participant" description="Select Manage in the participant ticket directory to inspect server-authoritative state." />}
    <Dialog open={!!confirmation} onClose={() => setConfirmation(null)} title={confirmation?.title || 'Confirm ticket action'} description={confirmation?.description}><div className="dialog-actions"><button className="product-button product-button--secondary" onClick={() => setConfirmation(null)}>Cancel</button><button className="product-button" onClick={() => void confirmAction()}>{confirmation?.action === 'issue' ? 'Issue tickets' : confirmation?.action === 'send' ? 'Queue emails' : confirmation?.action === 'resend' ? 'Resend ticket' : confirmation?.action === 'reissue' ? 'Reissue ticket' : 'Revoke ticket'}</button></div></Dialog>
  </>;
}

function CheckIn() { return <AttendanceDashboard />; }

function Communications() {
  return <><PageHeader eyebrow="Engagement" title="Communications" description="Campaigns are scheduled after the event-critical workflows." /><section className="panel-section"><SectionHeader title="Coming soon" description="Campaign sending is not available yet." /><p>Transactional invitations and QR ticket delivery use their existing authorized service. Marketing campaigns require separate consent, templates and delivery controls.</p></section></>;
}

function Reports() { return <AttendanceDashboard exportOnly />; }

const Team = GateStaffWorkspace;

function Branding() {
  return <><PageHeader eyebrow="Summit Events" title="Branding" description="Manage the published identity used by registration pages and ticket delivery." actions={<ButtonLink href="/branding.html">Open live brand editor</ButtonLink>} /><CapabilityNotice capability={capabilities.branding}>Draft editing, logo management, light and dark previews, publication, restoration and version history are connected in the live editor.</CapabilityNotice><div className="content-grid" style={{marginTop:22}}><section className="panel-section"><SectionHeader title="Published identity" description="Illustrative preview of the Summit Events tenant brand."/><div className="brand-specimen"><div className="brand-specimen-mark">S</div><div><strong>Summit Events</strong><p>Innovation with purpose.</p></div></div><div className="brand-swatches" aria-label="Brand color preview"><span style={{background:'#205b4a'}}>Primary</span><span style={{background:'#c36f42'}}>Accent</span><span style={{background:'#f7f6f3',color:'#20231f'}}>Surface</span></div></section><aside className="panel-section"><SectionHeader title="Publishing safeguards"/><ul><li>Contrast is validated before publication.</li><li>Semantic status and focus colors cannot be overridden.</li><li>Each publication creates attributable history.</li><li>Restoration creates a new version.</li></ul></aside></div><SettingRow title="Version history" description="Open the connected editor to inspect actual versions and audit records."><DataTable label="Branding capabilities" columns={['Capability','Mode']} rows={[["Draft and live preview",<StatusMark tone="success">Live</StatusMark>],["Logo upload and removal",<StatusMark tone="success">Live</StatusMark>],["Publish and restore",<StatusMark tone="success">Live</StatusMark>]]}/></SettingRow></>;
}

function Billing() {
  return <><PageHeader eyebrow="Organization" title="Billing" description="Review the intended subscription experience without creating financial records." /><CapabilityNotice capability={capabilities.subscriptions}>Paystack and NGN are approved directions, but pricing, trials, allowances, taxes and nonpayment behavior are still open.</CapabilityNotice>
    <SettingRow title="Current plan" description="No subscription is attached to this development tenant."><div className="demo-lock"><h3>Billing is not connected</h3><p>A live plan, payment state, renewal date or invoice cannot be shown until M2-02 is implemented.</p><button className="product-button" disabled>Choose a plan</button></div></SettingRow>
    <SettingRow title="Usage" description="Counters below describe future metering dimensions, not current usage."><DataTable label="Planned billing usage" columns={['Dimension','Current','Allowance']} rows={[["Active events",'—','Not decided'],["Registrations",'—','Not decided'],["Messages",'—','Not decided']]} /></SettingRow></>;
}

function Settings() {
  return <><PageHeader eyebrow="Summit Events" title="Settings" description="Manage identity, brand, domains, security boundaries and integrations." />
    <SettingRow title="Organization profile" description="Public identity is currently managed through versioned branding."><label>Display name<input value="Summit Events" readOnly /></label><p><ButtonLink href="/branding.html">Open live branding editor</ButtonLink></p></SettingRow>
    <SettingRow title="Domains" description="Claim and verify hostnames without bypassing platform activation."><p><StatusMark tone="success">Fallback domain active</StatusMark></p><p><ButtonLink href="/domains.html" secondary>Manage live domains</ButtonLink></p></SettingRow>
    <SettingRow title="Security" description="Host-bound cookies, CSRF and MFA remain enforced by the backend."><label><input type="checkbox" checked readOnly /> Require MFA for privileged staff</label><label><input type="checkbox" checked readOnly /> Secure host-only sessions</label></SettingRow>
    <SettingRow title="Integrations" description="Provider integrations need approved backend configuration."><div className="demo-lock"><h3>No self-service integrations yet</h3><p>SMTP, object storage and queue configuration remain operational settings. Campaign and billing providers are future milestones.</p></div></SettingRow>
    <SettingRow title="Data and privacy" description="Synthetic local testing notices are not legal approval."><p>Participant-linked data is designed for deletion after event end plus 90 days. Export and deletion operations require M5-03.</p><button className="product-button" disabled>Request data export</button></SettingRow></>;
}

const screens: Record<string, () => ReactNode> = { dashboard: Dashboard, events: Events, participants: Attendees, tickets: Tickets, 'check-in': CheckIn, 'gate-staff': Team, communications: Communications, reports: Reports, branding: Branding, billing: Billing, settings: Settings };

type Session = { email: string; role: string; tenant_id: string };
function OrganizerShell({ session, route, Screen, signOut }: { session: Session; route: string; Screen: () => ReactNode; signOut: () => Promise<void> }) {
  const { selectedEvent, loading } = useEventWorkspace();
  const detail = loading ? 'Loading events' : selectedEvent ? <><strong>{selectedEvent.name}</strong><span>{selectedEvent.status}</span></> : 'No events yet';
  return <AppShell product="Event Check-in" context={session.email} workspaceDetail={detail} route={screens[route] ? route : 'dashboard'} nav={nav} utility={<button className="product-button product-button--secondary" onClick={() => void signOut()}>Sign out</button>}><Screen /></AppShell>;
}

function Workspace() {
  const route = useHashRoute('dashboard'); const Screen = screens[route] || Dashboard;
  const [session, setSession] = useState<Session | null>(null);
  const [state, setState] = useState<'loading'|'ready'|'denied'>('loading');
  useEffect(() => { void getJson<Session>('/api/v1/auth/session').then(value => {
    setSession(value);
    setState(['tenant_owner', 'tenant_admin', 'organizer', 'manager'].includes(value.role) ? 'ready' : 'denied');
  }).catch(() => setState('denied')); }, []);
  async function signOut() { await mutateJson('/api/v1/auth/logout', {}); location.href = '/'; }
  if (state === 'loading') return <main className="session-gate" role="status">Checking organizer session…</main>;
  if (state === 'denied') return <main className="session-gate"><h1>Organizer access required</h1><p>Sign in with an authorized organizer account. Gate staff use the assigned scanner workspace.</p><a className="product-button" href={session?.role?.startsWith('gate_') ? '/gate.html' : '/'}>{session?.role?.startsWith('gate_') ? 'Open scanner' : 'Sign in'}</a></main>;
  return <EventWorkspaceProvider><OrganizerShell session={session!} route={route} Screen={Screen} signOut={signOut} /></EventWorkspaceProvider>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><Workspace /></StrictMode>);
