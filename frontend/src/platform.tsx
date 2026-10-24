import { StrictMode, useEffect, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { Button, Dialog, Field, Status, initializeTheme, setTheme, type Theme } from './ui';
import { describeDomain, type DomainState } from './domain-vocabulary';
import { getJson, ManagementApiError, mutateJson } from './management-api';
import './management.css';

type AuthState = 'loading' | 'login' | 'mfa' | 'enroll' | 'session';
type AuthResult = { state: AuthState; secret?: string; recovery_codes?: string[] };
type ProvisionResult = {
  tenant_id: string; fallback_domain_id: string; fallback_hostname: string;
  dns_record: string; dns_value: string; state: string;
};

function App() {
  const [theme, setCurrentTheme] = useState<Theme>(initializeTheme);
  const [state, setState] = useState<AuthState>('loading');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [secret, setSecret] = useState('');
  const [recovery, setRecovery] = useState(false);
  const [codes, setCodes] = useState<string[]>([]);
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [tenantId, setTenantId] = useState('');
  const [ownerEmail, setOwnerEmail] = useState('');
  const [proof, setProof] = useState<ProvisionResult | null>(null);
  const [domains, setDomains] = useState<DomainState[]>([]);
  const [reissueOpen, setReissueOpen] = useState(false);

  useEffect(() => {
    getJson('/api/v1/platform/auth/session').then(() => setState('session'))
      .catch(() => setState('login'));
  }, []);

  async function perform(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try { await action(); }
    catch (cause) {
      if (cause instanceof ManagementApiError && [401, 403].includes(cause.status)) {
        setState('login'); setSecret(''); setCodes([]); setProof(null); setDomains([]);
        setTenantId(''); setReissueOpen(false);
        setError('Your platform session is unavailable. Sign in again.');
      } else setError(cause instanceof Error ? cause.message : 'Request failed');
    }
    finally { setBusy(false); }
  }

  function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void perform(async () => {
      const result = await mutateJson<AuthResult>('/api/v1/platform/auth/login', { email, password }, true);
      setPassword(''); setSecret(''); setCodes([]); setState(result.state);
    });
  }

  function verify(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void perform(async () => {
      const result = await mutateJson<AuthResult>('/api/v1/platform/auth/mfa/verify',
        { code, recovery }, true);
      setCode(''); setSecret(''); setCodes(result.recovery_codes || []); setState('session');
    });
  }

  function createTenant(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void perform(async () => {
      const result = await mutateJson<ProvisionResult>('/api/v1/platform/tenants',
        { name, slug }, true);
      setProof(result); setTenantId(result.tenant_id);
      setNotice('Tenant reserved. Complete DNS, TLS and routing checks before activation.');
      setName(''); setSlug('');
    });
  }

  async function loadDomains() {
    const result = await getJson<{ domains: DomainState[] }>(
      `/api/v1/platform/tenants/${encodeURIComponent(tenantId)}/domains`);
    setDomains(result.domains);
  }

  function changeTheme() {
    const next = theme === 'light' ? 'dark' : 'light';
    setTheme(next); setCurrentTheme(next);
  }

  return <main className="management">
    <header><p className="brand">Event Check-in / Platform</p>
      <Button variant="secondary" onClick={changeTheme}>Use {theme === 'light' ? 'dark' : 'light'} theme</Button>
    </header>
    <h1>Tenant provisioning</h1>
    <p className="intro">Create a tenant, verify its fallback domain, then invite its first owner.</p>
    {error && <Status tone="danger" title="Action failed" instruction={error} announce="assertive" />}
    {notice && <Status tone="info" title="Next step" instruction={notice} announce="polite" />}

    {state === 'loading' && <p role="status">Checking your session…</p>}
    {state === 'login' && <form className="stack" onSubmit={signIn}>
      <Field label="Verified staff email" type="email" autoComplete="username" value={email}
        onChange={(event) => setEmail(event.target.value)} required />
      <Field label="Password" type="password" autoComplete="current-password" value={password}
        onChange={(event) => setPassword(event.target.value)} required />
      <Button type="submit" loading={busy}>Continue</Button>
    </form>}
    {(state === 'mfa' || state === 'enroll') && <section>
      <h2>Verify your identity</h2>
      {state === 'enroll' && <>
        <p>Set up an authenticator before platform access is granted.</p>
        <Button variant="secondary" loading={busy} onClick={() => void perform(async () => {
          const result = await mutateJson<{ secret: string }>('/api/v1/platform/auth/mfa/enroll', {}, true);
          setSecret(result.secret);
        })}>Show setup key</Button>
        {secret && <p className="proof">Authenticator key: {secret}</p>}
      </>}
      <form className="stack" onSubmit={verify}>
        <Field label={recovery ? 'Recovery code' : 'Authenticator code'} value={code}
          inputMode={recovery ? 'text' : 'numeric'} autoComplete="one-time-code"
          onChange={(event) => setCode(event.target.value)} required />
        {state === 'mfa' && <Button variant="tertiary" onClick={() => setRecovery(!recovery)}>
          {recovery ? 'Use authenticator' : 'Use a recovery code'}
        </Button>}
        <Button type="submit" loading={busy}>Verify</Button>
      </form>
    </section>}

    {state === 'session' && <>
      {codes.length > 0 && <Status tone="warning" title="Save recovery codes"
        instruction={<span className="proof">{codes.join(' · ')}</span>} />}
      <section><h2>Create tenant</h2>
        <form className="stack" onSubmit={createTenant}>
          <Field label="Tenant name" value={name} onChange={(event) => setName(event.target.value)} required />
          <Field label="Tenant slug" hint="Lowercase letters, numbers and hyphens." value={slug}
            onChange={(event) => setSlug(event.target.value)} required />
          <Button type="submit" loading={busy}>Reserve tenant</Button>
        </form>
        {proof && <div className="proof" role="status">
          <p>Fallback: {proof.fallback_hostname}</p>
          <p>DNS TXT name: {proof.dns_record}</p>
          <p>DNS TXT value: {proof.dns_value}</p>
          <p>This proof is shown once. Configure it before requesting a check.</p>
        </div>}
      </section>
      <section><h2>Domain status and approval</h2>
        <div className="stack">
          <Field label="Tenant ID" value={tenantId} onChange={(event) => setTenantId(event.target.value)} />
          <Button variant="secondary" disabled={!tenantId} loading={busy}
            onClick={() => void perform(loadDomains)}>Load domains</Button>
        </div>
        {domains.map((domain) => {
          const message = describeDomain(domain);
          return <div className="domain-row" key={domain.id}>
            <h3>{domain.hostname}</h3>
            <Status tone={message.tone} title={message.title} instruction={message.instruction} />
            <p className="muted">Ownership: {domain.ownership}. TLS: {domain.tls}. Routing: {domain.routing}.</p>
            <div className="actions">
              <Button variant="secondary" loading={busy} onClick={() => void perform(async () => {
                await mutateJson(`/api/v1/platform/tenants/${tenantId}/domains/${domain.id}/check`, {}, true);
                setNotice('Domain check requested. Refresh status after processing.');
              })}>Request check</Button>
              {domain.routing !== 'active' && <Button variant="tertiary" loading={busy}
                onClick={() => void perform(async () => {
                  const result = await mutateJson<{ dns_value: string }>(
                    `/api/v1/platform/tenants/${tenantId}/domains/${domain.id}/renew`, {}, true);
                  setProof({ tenant_id: tenantId, fallback_domain_id: domain.id,
                    fallback_hostname: domain.hostname,
                    dns_record: `_eventcheckin-verify.${domain.hostname}`,
                    dns_value: result.dns_value, state: 'reserved' });
                  await loadDomains();
                  setNotice('Replace the DNS TXT proof, then request a check.');
                })}>Renew proof</Button>}
              {domain.routing === 'ready' && <Button loading={busy} onClick={() => void perform(async () => {
                await mutateJson(`/api/v1/platform/tenants/${tenantId}/domains/${domain.id}/activate`, {}, true);
                await loadDomains();
              })}>Approve activation</Button>}
              {domain.routing === 'active' && domain.kind === 'custom' && <Button variant="destructive"
                loading={busy} onClick={() => void perform(async () => {
                  await mutateJson(`/api/v1/platform/tenants/${tenantId}/domains/${domain.id}/deactivate`, {}, true);
                  await loadDomains();
                })}>Deactivate domain</Button>}
            </div>
          </div>;
        })}
      </section>
      <section><h2>Invite first owner</h2>
        <form className="stack" onSubmit={(event) => {
          event.preventDefault();
          void perform(async () => {
            await mutateJson(`/api/v1/platform/tenants/${tenantId}/owner-invitations`,
              { email: ownerEmail }, true);
            setNotice('Owner invitation requested. Membership activates after acceptance and MFA.');
            setOwnerEmail('');
          });
        }}>
          <Field label="Owner email" type="email" value={ownerEmail} autoComplete="email"
            onChange={(event) => setOwnerEmail(event.target.value)} required />
          <Button type="submit" loading={busy} disabled={!tenantId}>Send owner invitation</Button>
        </form>
        <Button variant="secondary" disabled={!tenantId} onClick={() => setReissueOpen(true)}>
          Reissue pending invitation
        </Button>
        <Dialog open={reissueOpen} onClose={() => setReissueOpen(false)}
          title="Reissue owner invitation"
          description="The current invitation will stop working. A new 48-hour link will be sent to the same email address.">
          <div className="actions">
            <Button variant="secondary" onClick={() => setReissueOpen(false)}>Cancel</Button>
            <Button loading={busy} onClick={() => { setReissueOpen(false); void perform(async () => {
              await mutateJson(`/api/v1/platform/tenants/${tenantId}/owner-invitations/reissue`, {}, true);
              setNotice('The earlier invitation was revoked and a replacement was requested.');
            }); }}>Revoke and reissue</Button>
          </div>
        </Dialog>
      </section>
      <Button variant="tertiary" loading={busy} onClick={() => void perform(async () => {
        await mutateJson('/api/v1/platform/auth/logout', {}, true);
        setSecret(''); setCodes([]); setProof(null); setDomains([]);
        setTenantId(''); setReissueOpen(false); setState('login');
      })}>Sign out</Button>
    </>}
  </main>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
