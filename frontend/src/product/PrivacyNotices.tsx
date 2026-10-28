import { useEffect, useRef, useState, type FormEvent } from 'react';
import { getJson, mutateJson } from '../management-api';
import { ButtonLink, PageHeader, StatusMark } from './components';
import { Organization, OrganizationPage, organizationDetail, organizationPage } from './organization-api';

type Notice = {
  version: number;
  body: string;
  lawful_basis: string;
  test_only: boolean;
  created_at: string;
  created_by: string | null;
  approved_at: string | null;
  approved_by: string | null;
  approval_reference: string | null;
  active: boolean;
};
type NoticeList = { organization_id: string; organization_name: string; notices: Notice[] };

export function PrivacyNotices() {
  const initialTenant = new URLSearchParams(location.hash.split('?')[1] || '').get('organization') || '';
  const [tenantId, setTenantId] = useState(initialTenant);
  const [selectedOrganization, setSelectedOrganization] = useState<Organization | null>(null);
  const [organizations, setOrganizations] = useState<OrganizationPage | null>(null);
  const [searchInput, setSearchInput] = useState('');
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const [directoryLoading, setDirectoryLoading] = useState(false);
  const [directoryError, setDirectoryError] = useState('');
  const [directoryRefresh, setDirectoryRefresh] = useState(0);
  const selectionRequest = useRef(0);
  const [loaded, setLoaded] = useState<NoticeList | null>(null);
  const [body, setBody] = useState('');
  const [basis, setBasis] = useState('');
  const [testOnly, setTestOnly] = useState(false);
  const [approvalReference, setApprovalReference] = useState<Record<number, string>>({});
  const [approvalConfirmed, setApprovalConfirmed] = useState<number | null>(null);
  const [activationConfirmed, setActivationConfirmed] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  async function load(id: string) {
    setBusy(true); setError('');
    try { setLoaded(await getJson<NoticeList>(`/api/v1/platform/organizations/${encodeURIComponent(id)}/privacy-notices`)); }
    catch (cause) { setLoaded(null); setError(cause instanceof Error ? cause.message : 'Notice records unavailable.'); }
    finally { setBusy(false); }
  }
  useEffect(() => {
    let live = true;
    setDirectoryLoading(true); setDirectoryError('');
    void organizationPage(search, offset).then(result => { if (live) setOrganizations(result); })
      .catch(cause => { if (live) { setOrganizations(null); setDirectoryError(cause instanceof Error ? cause.message : 'Could not load organizations.'); } })
      .finally(() => { if (live) setDirectoryLoading(false); });
    return () => { live = false; };
  }, [search, offset, directoryRefresh]);
  useEffect(() => { if (initialTenant) void selectOrganization(initialTenant, false); }, []); // initial deep link only

  async function selectOrganization(id: string, updateUrl = true) {
    const request = ++selectionRequest.current;
    setTenantId(id); setLoaded(null); setSelectedOrganization(null); setError(''); setNotice('');
    if (updateUrl) history.replaceState(null, '', id ? `#privacy?organization=${encodeURIComponent(id)}` : '#privacy');
    if (!id) return;
    setBusy(true);
    try {
      const organization = await organizationDetail(id);
      if (request !== selectionRequest.current) return;
      setSelectedOrganization(organization);
      const notices = await getJson<NoticeList>(`/api/v1/platform/organizations/${encodeURIComponent(id)}/privacy-notices`);
      if (request === selectionRequest.current) setLoaded(notices);
    } catch (cause) {
      if (request === selectionRequest.current) setError(cause instanceof Error ? cause.message : 'Notice records unavailable.');
    } finally { if (request === selectionRequest.current) setBusy(false); }
  }

  function searchOrganizations(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setOffset(0); setSearch(searchInput.trim());
  }

  async function draft(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!loaded) return;
    setBusy(true); setError(''); setNotice('');
    try {
      await mutateJson(`/api/v1/platform/organizations/${loaded.organization_id}/privacy-notices`,
        { body, lawful_basis: basis, test_only: testOnly }, true);
      setBody(''); setBasis(''); setTestOnly(false); setNotice('Draft created. Review its exact text before approval.');
      await load(loaded.organization_id);
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Draft creation failed.'); }
    finally { setBusy(false); }
  }
  async function act(version: number, action: 'approve' | 'activate') {
    if (!loaded) return;
    setBusy(true); setError(''); setNotice('');
    try {
      await mutateJson(`/api/v1/platform/organizations/${loaded.organization_id}/privacy-notices/${version}/${action}`,
        action === 'approve' ? { approval_reference: approvalReference[version] || '', confirmed: approvalConfirmed === version } : { confirmed: activationConfirmed === version }, true);
      setApprovalReference({}); setApprovalConfirmed(null); setActivationConfirmed(null);
      setNotice(action === 'approve' ? `Version ${version} approved. Activate it when ready.` : `Version ${version} is active for this organization.`);
      await load(loaded.organization_id);
    } catch (cause) { setError(cause instanceof Error ? cause.message : `Notice ${action} failed.`); }
    finally { setBusy(false); }
  }

  return <><PageHeader eyebrow="Platform console" title="Privacy notices" description="Create an immutable notice, record external approval, then activate it for one organization." />
    <section className="panel-section"><h2>Choose organization</h2><p>Only a platform administrator with an MFA-verified session can manage notices. Organizer accounts have no approval access.</p>
      <form className="organization-search" onSubmit={searchOrganizations} role="search"><label htmlFor="privacy-organization-search">Find organization</label><div><input id="privacy-organization-search" value={searchInput} maxLength={100} onChange={event => setSearchInput(event.target.value)} placeholder="Name or organizer email"/><button className="product-button product-button--secondary" disabled={directoryLoading} type="submit">Search</button></div></form>
      {directoryLoading && <p role="status">Loading organizations…</p>}
      {directoryError && <p className="request-error" role="alert">{directoryError} <button className="text-action" onClick={() => setDirectoryRefresh(value => value + 1)}>Retry</button></p>}
      {!directoryLoading && !directoryError && organizations && <><label className="organization-selector">Organization<select value={tenantId} onChange={event => void selectOrganization(event.target.value)}><option value="">Select an organization</option>
        {selectedOrganization && !organizations.organizations.some(item => item.id === selectedOrganization.id) && <option value={selectedOrganization.id}>{selectedOrganization.name}</option>}
        {organizations.organizations.map(item => <option key={item.id} value={item.id}>{item.name}{item.primary_organizer ? ` · ${item.primary_organizer}` : ''}</option>)}
      </select></label><p className="directory-count" role="status">{organizations.total ? `Showing ${organizations.offset + 1}–${organizations.offset + organizations.organizations.length} of ${organizations.total}` : search ? 'No matching organizations. Try another search.' : 'No organizations yet. Create one first.'}</p>
        {organizations.total > organizations.limit && <div className="page-actions"><button className="product-button product-button--secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - organizations.limit))}>Previous</button><button className="product-button product-button--secondary" disabled={!organizations.has_more} onClick={() => setOffset(offset + organizations.limit)}>Next</button></div>}
      </>}
      {busy && <p role="status">Loading or saving notice…</p>}{error && <p className="request-error" role="alert">{error}</p>}{notice && <p className="success-banner" role="status">{notice}</p>}
    </section>
    {!tenantId && <p className="form-help">Choose an organization to view or manage its privacy notices.</p>}
    {loaded && <><section className="panel-section"><h2>{loaded.organization_name}</h2><p>No participant records are exposed here. One approved notice may be active at a time.</p>
      {loaded.notices.length ? loaded.notices.map(item => <article className="notice-record" key={item.version}>
        <h3>Version {item.version} <StatusMark tone={item.active ? 'success' : item.approved_at ? 'neutral' : 'warning'}>{item.active ? 'Active' : item.approved_at ? 'Approved' : 'Draft'}</StatusMark></h3>
        <p className="notice-body">{item.body}</p><p><strong>Recorded basis:</strong> {item.lawful_basis}</p>
        <p><strong>Created:</strong> {new Date(item.created_at).toLocaleString()} · <strong>Actor:</strong> <code>{item.created_by || 'Legacy record'}</code></p>
        {item.approved_at && <p><strong>Approved:</strong> {new Date(item.approved_at).toLocaleString()} · <strong>Actor:</strong> <code>{item.approved_by || 'Legacy record'}</code></p>}
        {item.test_only && <p>Test-only notice. Activation is restricted to local and test environments.</p>}
        {item.approval_reference && <p><strong>Approval reference:</strong> {item.approval_reference}</p>}
        {!item.approved_at && <div className="form-grid"><label>External approval reference for version {item.version}<input value={approvalReference[item.version] || ''} maxLength={500} onChange={event => setApprovalReference(current => ({...current, [item.version]: event.target.value}))}/></label><label className="import-authorization"><input type="checkbox" checked={approvalConfirmed === item.version} onChange={event => setApprovalConfirmed(event.target.checked ? item.version : null)}/><span>I confirm this exact notice and basis received the required external approval.</span></label><button className="product-button" disabled={busy || approvalConfirmed !== item.version || !approvalReference[item.version]?.trim()} onClick={() => void act(item.version, 'approve')}>Record approval</button></div>}
        {item.approved_at && !item.active && <div><label className="import-authorization"><input type="checkbox" checked={activationConfirmed === item.version} onChange={event => setActivationConfirmed(event.target.checked ? item.version : null)}/><span>Activate this approved version for new registrations and imports.</span></label><button className="product-button" disabled={busy || activationConfirmed !== item.version} onClick={() => void act(item.version, 'activate')}>Activate version {item.version}</button></div>}
      </article>) : <p>No notice has been drafted for this organization.</p>}
    </section><section className="panel-section"><h2>Draft a new notice</h2><p>Draft text and lawful basis cannot be edited after creation. Create a new version to correct either field. Test-only copy cannot be activated in a remote environment.</p>
      <form onSubmit={event => void draft(event)} className="form-grid"><label>Notice text<textarea required minLength={1} maxLength={20_000} rows={7} value={body} onChange={event => setBody(event.target.value)}/></label><label>Recorded lawful basis<textarea required minLength={1} maxLength={500} rows={3} value={basis} onChange={event => setBasis(event.target.value)}/></label><label className="import-authorization"><input type="checkbox" checked={testOnly} onChange={event => setTestOnly(event.target.checked)}/><span>Test-only notice for synthetic local or test data</span></label><button className="product-button" disabled={busy || !body.trim() || !basis.trim()} type="submit">Create draft</button></form>
    </section></>}
    <p><ButtonLink href="#organizations" secondary>Back to organizations</ButtonLink></p>
  </>;
}
