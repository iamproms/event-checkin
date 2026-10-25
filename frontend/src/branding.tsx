import { StrictMode, useEffect, useState, type FormEvent } from 'react';
import { createRoot } from 'react-dom/client';
import { Button, Dialog, Field, Status, initializeTheme, setTheme, type Theme } from './ui';
import { getJson, ManagementApiError, mutateJson } from './management-api';
import { TenantBrandMark } from './tenant-brand';
import './branding.css';

type Branding = {
  display_name: string; logo_url: string | null; primary_color: string | null;
  accent_color: string | null; action_text_color: string | null; sender_name: string | null;
  revision: number; published_version: number | null;
};
type Version = { version: number; display_name: string; published_at: string;
  restored_from_version: number | null; has_logo: boolean };
type Audit = { action: string; version: number | null; actor_user_id: string; occurred_at: string };
type Editor = Pick<Branding, 'display_name' | 'primary_color' | 'accent_color' | 'sender_name'>;

function draftEditor(value: Branding): Editor {
  return { display_name: value.display_name, primary_color: value.primary_color,
    accent_color: value.accent_color, sender_name: value.sender_name ?? value.display_name };
}

function validColor(value: string | null) { return !!value && /^#[\da-fA-F]{6}$/.test(value); }

function foreground(color: string): string {
  const rgb = [1, 3, 5].map((index) => Number.parseInt(color.slice(index, index + 2), 16) / 255);
  const linear = rgb.map((channel) => channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4);
  const luminance = 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
  return (1.05 / (luminance + 0.05)) >= 4.5 ? '#ffffff' : '#111817';
}

function Preview({ title, theme, editor, logo }: { title: string; theme: 'light' | 'dark';
  editor: Editor; logo: string | null }) {
  const primary = validColor(editor.primary_color) ? editor.primary_color! : theme === 'light' ? '#205b4a' : '#a6d7c5';
  const text = validColor(editor.primary_color) ? foreground(primary) : theme === 'light' ? '#ffffff' : '#111817';
  const accent = validColor(editor.accent_color) ? editor.accent_color! : theme === 'light' ? '#205b4a' : '#a6d7c5';
  return <div className={`branding-preview branding-preview--${theme}`}>
    <h3>{title}</h3>
    <div className="branding-preview__identity">{logo && <img className="branding-preview__logo" src={logo} alt="" />}
      <strong>{editor.display_name.trim() || 'Your organization'}</strong></div>
    <span className="branding-preview__action" style={{ backgroundColor: primary, color: text,
      borderColor: primary }}>Register for this event</span>
    <p className="branding-preview__accent" style={{ borderColor: accent }}>Event information and entry instructions.</p>
  </div>;
}

function App() {
  const [theme, setCurrentTheme] = useState<Theme>(initializeTheme);
  const [saved, setSaved] = useState<Branding | null>(null);
  const [editor, setEditor] = useState<Editor | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [confirm, setConfirm] = useState<{ action: 'publish' | 'restore'; version?: number } | null>(null);

  async function load() {
    const [draft, history] = await Promise.all([
      getJson<Branding>('/api/v1/branding/draft'),
      getJson<{ versions: Version[]; audit: Audit[] }>('/api/v1/branding/history'),
    ]);
    setSaved(draft); setEditor(draftEditor(draft)); setVersions(history.versions); setAudit(history.audit);
  }
  useEffect(() => { void load().catch((cause) => setError(
    cause instanceof ManagementApiError && [401, 403].includes(cause.status)
      ? 'Branding access is unavailable. Sign in to a tenant owner or administrator account.'
      : 'Could not load branding. Try again.'
  )); }, []);

  async function perform(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true); setError(''); setNotice('');
    try { await action(); }
    catch (cause) {
      if (cause instanceof ManagementApiError && [401, 403].includes(cause.status)) {
        setSaved(null); setEditor(null); setVersions([]); setAudit([]);
        setError('Branding access is unavailable. Sign in to an authorized tenant again.');
      } else setError(cause instanceof Error ? cause.message : 'The request failed.');
    }
    finally { setBusy(false); setConfirm(null); }
  }

  const dirty = saved && editor && JSON.stringify(draftEditor(saved)) !== JSON.stringify(editor);
  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!saved || !editor) return;
    void perform(async () => {
      const result = await mutateJson<Branding>('/api/v1/branding/draft',
        { ...editor, revision: saved.revision }, false, 'PUT');
      setSaved(result); setEditor(draftEditor(result)); setNotice('Draft saved. Review both previews before publishing.');
    });
  }

  async function sendLogo(file: File) {
    const csrf = await getJson<{ csrf_token: string }>('/api/v1/auth/csrf');
    const response = await fetch('/api/v1/branding/logo', {
      method: 'PUT', credentials: 'same-origin', cache: 'no-store',
      headers: { 'content-type': file.type, 'x-csrf-token': csrf.csrf_token }, body: file,
    });
    const result = await response.json() as Branding & { detail?: { message?: string } };
    if (!response.ok) throw new ManagementApiError(result.detail?.message || 'Logo upload failed', response.status);
    setSaved(result); setNotice('Logo added to the draft. Publish to make it visible to attendees.');
  }

  function changeTheme() { const next = theme === 'light' ? 'dark' : 'light';
    setTheme(next); setCurrentTheme(next); }

  return <main className="management branding-main">
    <header><p className="brand"><TenantBrandMark area="Branding" /></p>
      <Button variant="secondary" onClick={changeTheme}>Use {theme === 'light' ? 'dark' : 'light'} theme</Button></header>
    <h1>Tenant branding</h1>
    <p className="intro branding-intro">Give your registration and ticket experience a clear identity. Changes stay in a draft until you publish them.</p>
    {error && <Status tone="danger" title="Action failed" instruction={error} announce="assertive" />}
    {notice && <Status tone="info" title="Update" instruction={notice} announce="polite" />}
    {!editor || !saved ? <Status tone="info" title="Branding unavailable" instruction="Refresh after signing in to an authorized tenant." /> : <>
      <section><h2>Identity and colors</h2>
        <form onSubmit={save} className="branding-fields">
          <Field className="wide" label="Display name" value={editor.display_name} required maxLength={120}
            onChange={(event) => setEditor({ ...editor, display_name: event.target.value })} />
          <Field label="Primary color" value={editor.primary_color ?? ''} placeholder="#46806A"
            hint="Six-digit hex. Must work on light and dark surfaces."
            onChange={(event) => setEditor({ ...editor, primary_color: event.target.value || null })} />
          <Field label="Accent color" value={editor.accent_color ?? ''} placeholder="#46806A"
            hint="Used for accents, never success, warning, error or focus."
            onChange={(event) => setEditor({ ...editor, accent_color: event.target.value || null })} />
          <Field className="wide" label="Sender display name" value={editor.sender_name ?? ''} required maxLength={100}
            hint="This does not verify an email sender domain."
            onChange={(event) => setEditor({ ...editor, sender_name: event.target.value })} />
          <div className="actions wide"><Button type="submit" loading={busy}>Save draft</Button>
            {dirty && <span className="muted" role="status">Unsaved changes</span>}</div>
        </form>
      </section>
      <section><h2>Logo</h2><p>PNG, JPEG or WebP, up to 2 MB. Images are decoded and stored as private PNG files. SVG and animated files are unavailable.</p>
        <div className="branding-file"><label htmlFor="branding-logo">Choose logo</label>
          <input id="branding-logo" type="file" accept="image/png,image/jpeg,image/webp"
            onChange={(event) => { const file = event.target.files?.[0]; if (!file) return;
              void perform(async () => { await sendLogo(file); }); }} /></div>
        {saved.logo_url && <div className="actions"><Button variant="secondary" loading={busy} onClick={() => void perform(async () => {
          const csrf = await getJson<{ csrf_token: string }>('/api/v1/auth/csrf');
          const response = await fetch('/api/v1/branding/logo', { method: 'DELETE', credentials: 'same-origin',
            headers: { 'x-csrf-token': csrf.csrf_token } });
          const result = await response.json() as Branding & { detail?: { message?: string } };
          if (!response.ok) throw new ManagementApiError(result.detail?.message || 'Logo removal failed', response.status);
          setSaved(result); setNotice('Logo removed from the draft. Publish to remove it from attendee views.');
        })}>Remove draft logo</Button></div>}
      </section>
      <section><h2>Preview</h2><p>Check the same branding in both themes. Platform status and focus colors stay unchanged.</p>
        <div className="branding-previews">
          <Preview title="Light" theme="light" editor={editor} logo={saved.logo_url ? `${saved.logo_url}?r=${saved.revision}` : null} />
          <Preview title="Dark" theme="dark" editor={editor} logo={saved.logo_url ? `${saved.logo_url}?r=${saved.revision}` : null} />
        </div><div className="actions"><Button disabled={!!dirty || busy} onClick={() => setConfirm({ action: 'publish' })}>Publish branding</Button></div>
        {dirty && <p className="muted">Save the draft before publishing.</p>}
      </section>
      <section><h2>Published history</h2>
        {versions.length === 0 ? <Status tone="info" title="No published branding" instruction="Publish your reviewed draft to create the first version." /> :
          <ol className="branding-history">{versions.map((version) => <li key={version.version}>
            <div><strong>Version {version.version}</strong><p>{version.display_name}</p>
              <p className="muted">{new Date(version.published_at).toLocaleString()}{version.restored_from_version ? ` · Restored from version ${version.restored_from_version}` : ''}</p></div>
            <Button variant="secondary" disabled={busy || version.version === saved.published_version}
              onClick={() => setConfirm({ action: 'restore', version: version.version })}>Restore version {version.version}</Button>
          </li>)}</ol>}
      </section>
      <section><h2>Change history</h2>
        {audit.length === 0 ? <p className="muted">No branding changes recorded yet.</p> :
          <ol className="branding-history">{audit.map((entry, index) => <li key={`${entry.occurred_at}-${index}`}>
            <div><strong>{entry.action.replaceAll('.', ' ')}</strong>
              <p className="muted">{new Date(entry.occurred_at).toLocaleString()} · Actor {entry.actor_user_id}
                {entry.version ? ` · Version ${entry.version}` : ''}</p></div>
          </li>)}</ol>}
      </section>
      <Dialog open={!!confirm} onClose={() => setConfirm(null)}
        title={confirm?.action === 'publish' ? 'Publish branding?' : 'Restore branding?'}
        description={confirm?.action === 'publish' ? 'Your saved draft will become visible on tenant-facing pages.' :
          `Version ${confirm?.version} will become a new published version. Current branding remains in history.`}>
        <div className="branding-confirm"><Button loading={busy} onClick={() => void perform(async () => {
          if (confirm?.action === 'publish') {
            await mutateJson('/api/v1/branding/publish', { revision: saved.revision });
            setNotice('Branding published.');
          } else if (confirm?.version) {
            await mutateJson(`/api/v1/branding/restore/${confirm.version}`, {});
            setNotice(`Branding restored from version ${confirm.version}.`);
          }
          await load();
        })}>Confirm {confirm?.action === 'publish' ? 'publish' : 'restore'}</Button>
          <Button variant="tertiary" onClick={() => setConfirm(null)}>Cancel</Button></div>
      </Dialog>
    </>}
  </main>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
