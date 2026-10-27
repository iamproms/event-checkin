import { StrictMode, useEffect, useState, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { AppShell, type NavItem } from './product/AppShell';
import { capabilities } from './product/capabilities';
import { ButtonLink, CapabilityNotice, DataTable, EmptyState, PageHeader, SectionHeader, SettingRow, StatusMark } from './product/components';
import { useHashRoute } from './product/router';
import { getJson, mutateJson } from './management-api';
import { AttendanceDashboard, EventPicker, GateStaffWorkspace, LiveEventsDirectory, ParticipantsWorkspace, useEvents } from './features/event-critical';
import './product/product.css';

const nav: NavItem[] = [
  { route: 'dashboard', label: 'Dashboard', icon: 'overview' }, { route: 'events', label: 'Events', icon: 'events' },
  { route: 'participants', label: 'Participants', icon: 'attendees' }, { route: 'tickets', label: 'Tickets', icon: 'tickets' },
  { route: 'check-in', label: 'Check-in', icon: 'checkin' }, { route: 'gate-staff', label: 'Gate staff', icon: 'team' },
  { route: 'communications', label: 'Communications', icon: 'messages', badge: 'Soon' }, { route: 'reports', label: 'Reports', icon: 'reports' },
  { route: 'branding', label: 'Branding', icon: 'organizations' }, { route: 'settings', label: 'Settings', icon: 'settings' },
];

function Dashboard() {
  return <AttendanceDashboard />;
}

const Events = LiveEventsDirectory;
const Attendees = ParticipantsWorkspace;

type TicketState = { ticket_status: string; delivery_status: string; delivery_error?: string | null };
type BulkTicketState = { registered: number; issued: number; queued: number; sent: number; delivered: number; failed: number };
function Tickets() {
  const params = new URLSearchParams(location.hash.split('?')[1] || '');
  const { events } = useEvents();
  const [bulkEventId, setBulkEventId] = useState(params.get('event') || '');
  const activeBulkEvent = bulkEventId || events.find(item => item.status === 'published')?.id || events[0]?.id || '';
  const bulkEvent = events.find(item => item.id === activeBulkEvent);
  const [bulkState, setBulkState] = useState<BulkTicketState | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  const [bulkError, setBulkError] = useState('');
  const [bulkNotice, setBulkNotice] = useState('');
  const [showEmailPreview, setShowEmailPreview] = useState(false);
  const [eventId, setEventId] = useState(params.get('event') || ''); const [registrationId, setRegistrationId] = useState(params.get('registration') || '');
  const [ticket, setTicket] = useState<TicketState | null>(null); const [error, setError] = useState(''); const [busy, setBusy] = useState(false);
  const path = `/api/v1/events/${encodeURIComponent(eventId)}/registrations/${encodeURIComponent(registrationId)}/ticket`;
  async function load() { setBusy(true); setError(''); try { setTicket(await getJson<TicketState>(path)); } catch (cause) { setError(cause instanceof Error ? cause.message : 'Ticket could not be loaded.'); } finally { setBusy(false); } }
  async function command(action: 'resend'|'reissue'|'revoke') { setBusy(true); setError(''); try { setTicket(await mutateJson<TicketState>(`${path}/${action}`, {})); } catch (cause) { setError(cause instanceof Error ? cause.message : 'Ticket action failed.'); } finally { setBusy(false); } }
  async function refreshBulk() { if (!activeBulkEvent) return; setBulkBusy(true); setBulkError(''); try { setBulkState(await getJson<BulkTicketState>(`/api/v1/events/${encodeURIComponent(activeBulkEvent)}/tickets/bulk`)); } catch (cause) { setBulkError(cause instanceof Error ? cause.message : 'Ticket totals could not be loaded.'); } finally { setBulkBusy(false); } }
  useEffect(() => { setBulkState(null); if (activeBulkEvent) void refreshBulk(); }, [activeBulkEvent]);
  async function bulkCommand(action: 'issue' | 'send') {
    if (!activeBulkEvent) return;
    const text = action === 'issue' ? 'Queue secure QR issuance for eligible imported registrations?' : 'Queue transactional ticket email for all issued imported tickets without a prior send? Confirm the approved notice, sender, and test transport before continuing.';
    if (!window.confirm(text)) return;
    setBulkBusy(true); setBulkError(''); setBulkNotice('');
    try { const result = await mutateJson<Record<string, number>>(`/api/v1/events/${encodeURIComponent(activeBulkEvent)}/tickets/bulk/${action}`, {}); setBulkNotice(action === 'issue' ? `${result.queued_or_existing ?? 0} eligible registrations are queued or already issued.` : `${result.newly_queued ?? 0} new messages queued. “Sent” means provider acceptance, not inbox delivery.`); setBulkState(await getJson<BulkTicketState>(`/api/v1/events/${encodeURIComponent(activeBulkEvent)}/tickets/bulk`)); }
    catch (cause) { setBulkError(cause instanceof Error ? cause.message : 'The bulk action failed.'); }
    finally { setBulkBusy(false); }
  }
  return <><PageHeader eyebrow="Innovation Summit 2026" title="Tickets" description="Inspect delivery state and use credential-safe support actions." /><CapabilityNotice capability={capabilities.tickets}>Ticket commands are live only when an authorized operator supplies an existing event and registration ID. Credentials are never returned here.</CapabilityNotice>
    <section className="panel-section"><SectionHeader title="Imported attendee tickets" description="Issue first, review the message, then queue email separately." />
      <div className="toolbar-row"><EventPicker events={events} value={activeBulkEvent} onChange={setBulkEventId}/><button className="product-button product-button--secondary" disabled={bulkBusy || !activeBulkEvent} onClick={() => void refreshBulk()}>{bulkBusy ? 'Refreshing…' : 'Refresh progress'}</button></div>
      {bulkState && <DataTable label="Imported ticket progress" columns={['Registrations','Issued','Queued','Provider accepted','Delivered signal','Failed']} rows={[[bulkState.registered,bulkState.issued,bulkState.queued,bulkState.sent,bulkState.delivered,bulkState.failed]]} />}
      <div className="page-actions"><button className="product-button" disabled={bulkBusy || !activeBulkEvent || bulkEvent?.status !== 'published'} onClick={() => void bulkCommand('issue')}>Issue QR tickets</button><button className="product-button product-button--secondary" disabled={!activeBulkEvent} onClick={() => setShowEmailPreview(value => !value)}>{showEmailPreview ? 'Hide email preview' : 'Preview ticket email'}</button><button className="product-button" disabled={bulkBusy || !activeBulkEvent || !bulkState?.issued} onClick={() => void bulkCommand('send')}>Queue ticket emails</button></div>
      {showEmailPreview && <div className="ticket-email-preview"><p><strong>Preview only · no recipient or credential</strong></p><h3>Your ticket for {bulkEvent?.name || 'the event'}</h3><p>{bulkEvent?.starts_at ? new Date(bulkEvent.starts_at).toLocaleString() : 'Event date'} · {bulkEvent?.location || 'Venue to be confirmed'}</p><p>Present your unique QR code at the gate. Keep it private; the first valid scan uses it.</p><p>For ticket help, contact the event organizer.</p><p>The delivery worker inserts each attendee’s unique QR image. This preview does not send email.</p></div>}
      {bulkNotice && <p role="status">{bulkNotice}</p>}{bulkError && <p className="request-error" role="alert">{bulkError}</p>}
    </section>
    <SettingRow title="Find a ticket" description="Use known identifiers from an approved support workflow. The backend has no ticket directory yet."><label>Event ID<input placeholder="Event UUID" value={eventId} onChange={event=>setEventId(event.target.value)} /></label><label>Registration ID<input placeholder="Registration UUID" value={registrationId} onChange={event=>setRegistrationId(event.target.value)} /></label><button className="product-button" type="button" disabled={busy || !eventId || !registrationId} onClick={()=>void load()}>{busy?'Loading…':'Load ticket state'}</button>{error && <p role="alert" className="status-mark status-mark--danger">{error}</p>}</SettingRow>
    <section className="panel-section"><SectionHeader title="Credential lifecycle" description="Support actions preserve the bearer-credential security contract." /><DataTable label="Ticket action behavior" columns={['Action','Credential','Delivery','Confirmation']} rows={[[<strong>Resend</strong>,'Keeps active credential','Creates idempotent delivery','Required'],[<strong>Reissue</strong>,'Revokes previous credential','Creates replacement delivery','Required'],[<strong>Revoke</strong>,'Prevents future redemption','No new delivery','Required']]} /></section>
    {ticket ? <section className="panel-section"><SectionHeader title="Authoritative ticket state" description="The credential itself is never returned."/><DataTable label="Ticket state" columns={['Ticket','Delivery','Provider error']} rows={[[<StatusMark tone={ticket.ticket_status==='active'?'success':'danger'}>{ticket.ticket_status}</StatusMark>,<StatusMark tone={ticket.delivery_status==='sent'||ticket.delivery_status==='delivered'?'success':ticket.delivery_status==='failed'?'danger':'warning'}>{ticket.delivery_status}</StatusMark>,ticket.delivery_error || '—']]} /><div className="page-actions" style={{marginTop:16}}><button className="product-button product-button--secondary" disabled={busy} onClick={()=>void command('resend')}>Resend</button><button className="product-button product-button--secondary" disabled={busy} onClick={()=>confirm('Reissue this ticket and revoke its current credential?')&&void command('reissue')}>Reissue</button><button className="product-button" disabled={busy || ticket.ticket_status!=='active'} onClick={()=>confirm('Revoke this ticket? It will no longer be redeemable.')&&void command('revoke')}>Revoke</button></div></section> : <EmptyState icon="tickets" title="No ticket loaded" description="Enter both identifiers to inspect authoritative ticket and delivery state. A ticket preview is intentionally unavailable because the API never exposes credentials." />}
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
  return <AppShell product="Event Check-in" context={session?.email || 'Organizer'} route={screens[route] ? route : 'dashboard'} nav={nav} utility={<button className="product-button product-button--secondary" onClick={() => void signOut()}>Sign out</button>}><Screen /></AppShell>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><Workspace /></StrictMode>);
