import { StrictMode, useEffect, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { PlatformConsole } from './product/PlatformConsole';
import { capabilities } from './product/capabilities';
import { ButtonLink, CapabilityNotice, PageHeader } from './product/components';
import { getJson, mutateJson } from './management-api';
import './product/product.css';

function Organizations() {
  type Created = { organization_id: string; organizer_email: string; invitation_delivery_status: string; event_setup_name: string };
  const [authorized, setAuthorized] = useState(false);
  const [checked, setChecked] = useState(false);
  const [name, setName] = useState(''); const [email, setEmail] = useState('');
  const [organizerName, setOrganizerName] = useState(''); const [phone, setPhone] = useState(''); const [eventName, setEventName] = useState('');
  const [key, setKey] = useState(() => crypto.randomUUID());
  const [created, setCreated] = useState<Created | null>(null);
  const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  useEffect(() => { void getJson('/api/v1/platform/auth/session').then(() => setAuthorized(true)).catch(() => setAuthorized(false)).finally(() => setChecked(true)); }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    try { setCreated(await mutateJson<Created>('/api/v1/platform/organizations', { name, organizer_email: email, organizer_name: organizerName || null, contact_phone: phone || null, event_name: eventName || null, idempotency_key: key }, true)); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Organization creation failed.'); }
    finally { setBusy(false); }
  }
  async function resend() { if (!created) return; setBusy(true); setError(''); try { setCreated(await mutateJson<Created>(`/api/v1/platform/organizations/${encodeURIComponent(created.organization_id)}/invitation/resend`, {}, true)); } catch (cause) { setError(cause instanceof Error ? cause.message : 'Invitation resend failed.'); } finally { setBusy(false); } }
  return <><PageHeader eyebrow="Platform console" title="Organizations" description="Create an organization and invite its first organizer on the shared application host." />
    <section className="panel-section"><h2>Create organization</h2><p>Organization access uses verified membership and MFA. Custom domain setup is optional.</p>
      {!checked ? <p role="status">Checking platform access…</p> : !authorized ? <p>Sign in with a platform administrator account and complete MFA before creating an organization. <ButtonLink href="/">Open shared sign in</ButtonLink></p> : created ? <div role="status"><h3>{name} created</h3><p>Organizer: {created.organizer_email}</p><p>Invitation transport: <strong>{created.invitation_delivery_status.replaceAll('_', ' ')}</strong>. Provider acceptance does not prove inbox delivery.</p>{created.event_setup_name && <p>Suggested first event: {created.event_setup_name}. The organizer will set its schedule in Events.</p>}<p>Internal organization ID: <code>{created.organization_id}</code></p><div className="page-actions"><button className="product-button product-button--secondary" disabled={busy} onClick={() => void resend()}>{busy ? 'Sending…' : 'Resend account setup invitation'}</button><button className="product-button" onClick={() => { setCreated(null); setName(''); setEmail(''); setOrganizerName(''); setPhone(''); setEventName(''); setKey(crypto.randomUUID()); }}>Create another organization</button></div></div> : <form className="organization-create-form" onSubmit={event => void submit(event)}><label>Organization name<input required maxLength={200} value={name} onChange={event => setName(event.target.value)} /></label><label>Organizer email<input required type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} /></label><label>Organizer name <span>(optional)</span><input maxLength={160} value={organizerName} onChange={event => setOrganizerName(event.target.value)} /></label><label>Contact phone <span>(optional)</span><input type="tel" maxLength={40} value={phone} onChange={event => setPhone(event.target.value)} /></label><label>First event name <span>(optional)</span><input maxLength={200} value={eventName} onChange={event => setEventName(event.target.value)} /></label><button className="product-button" type="submit" disabled={busy}>{busy ? 'Creating…' : 'Create and invite organizer'}</button></form>}
      {error && <p className="request-error" role="alert">{error}</p>}
    </section><CapabilityNotice capability={capabilities.platformOrganizations}>Platform administrators can create organizations and invite owners. Participant records remain tenant-scoped and unavailable to platform sessions.</CapabilityNotice></>;
}
createRoot(document.getElementById('root')!).render(<StrictMode><PlatformConsole provisioning={<Organizations/>}/></StrictMode>);
