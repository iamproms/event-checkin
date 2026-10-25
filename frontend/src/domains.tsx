import { StrictMode, useEffect, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { Button, Field, Status, initializeTheme, setTheme, type Theme } from './ui';
import { describeDomain, type DomainState } from './domain-vocabulary';
import { getJson, ManagementApiError, mutateJson } from './management-api';
import { TenantBrandMark } from './tenant-brand';
import './management.css';

type ClaimResult = { domain_id: string; dns_record: string; dns_value: string };

function App() {
  const [theme, setCurrentTheme] = useState<Theme>(initializeTheme);
  const [domains, setDomains] = useState<DomainState[]>([]);
  const [hostname, setHostname] = useState('');
  const [proof, setProof] = useState<ClaimResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load() {
    const result = await getJson<{ domains: DomainState[] }>('/api/v1/domains');
    setDomains(result.domains);
  }
  useEffect(() => { void load().catch((cause) => {
    setError(cause instanceof Error ? cause.message : 'Could not load domains');
  }); }, []);
  async function perform(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try { await action(); }
    catch (cause) {
      if (cause instanceof ManagementApiError && [401, 403].includes(cause.status)) {
        setDomains([]); setProof(null);
        setError('Domain access is unavailable. Sign in to an authorized tenant again.');
      } else setError(cause instanceof Error ? cause.message : 'Request failed');
    }
    finally { setBusy(false); }
  }
  function claim(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void perform(async () => {
      const result = await mutateJson<ClaimResult>('/api/v1/domains', { hostname });
      setProof(result); setHostname(''); await load();
      setNotice('Add the TXT proof, then request a domain check. Platform approval controls activation.');
    });
  }
  function changeTheme() {
    const next = theme === 'light' ? 'dark' : 'light';
    setTheme(next); setCurrentTheme(next);
  }

  return <main className="management">
    <header><p className="brand"><TenantBrandMark area="Domains" /></p>
      <Button variant="secondary" onClick={changeTheme}>Use {theme === 'light' ? 'dark' : 'light'} theme</Button>
    </header>
    <h1>Web domains</h1>
    <p className="intro">Verify ownership before a platform administrator activates a custom hostname.</p>
    {error && <Status tone="danger" title="Action failed" instruction={error} announce="assertive" />}
    {notice && <Status tone="info" title="Next step" instruction={notice} announce="polite" />}
    <section><h2>Request a domain claim</h2>
      <form className="stack" onSubmit={claim}>
        <Field label="Custom hostname" type="text" autoComplete="url" value={hostname}
          hint="Enter the full hostname you control." onChange={(event) => setHostname(event.target.value)} required />
        <Button type="submit" loading={busy}>Request claim</Button>
      </form>
      {proof && <div className="proof" role="status">
        <p>DNS TXT name: {proof.dns_record}</p>
        <p>DNS TXT value: {proof.dns_value}</p>
        <p>This proof is shown once. Add it to DNS before checking.</p>
      </div>}
    </section>
    <section><h2>Current domains</h2>
      {domains.length === 0 && <p className="muted">No domains are available to this account.</p>}
      {domains.map((domain) => {
        const message = describeDomain(domain);
        return <div className="domain-row" key={domain.id}>
          <h3>{domain.hostname}</h3>
          <Status tone={message.tone} title={message.title} instruction={message.instruction} />
          <p className="muted">Ownership: {domain.ownership}. TLS: {domain.tls}. Routing: {domain.routing}.</p>
          <Button variant="secondary" loading={busy} onClick={() => void perform(async () => {
            await mutateJson(`/api/v1/domains/${domain.id}/check`, {});
            setNotice('Domain check requested. Refresh status after processing.');
          })}>Request check</Button>
          {domain.kind === 'custom' && domain.routing !== 'active' && <Button variant="tertiary"
            loading={busy} onClick={() => void perform(async () => {
              const result = await mutateJson<{ dns_value: string }>(`/api/v1/domains/${domain.id}/renew`, {});
              setProof({ domain_id: domain.id, dns_record: `_eventcheckin-verify.${domain.hostname}`,
                dns_value: result.dns_value });
              await load();
              setNotice('Replace the DNS TXT proof, then request a check.');
            })}>Renew proof</Button>}
        </div>;
      })}
      <div className="actions"><Button variant="tertiary" loading={busy}
        onClick={() => void perform(load)}>Refresh status</Button></div>
    </section>
  </main>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
