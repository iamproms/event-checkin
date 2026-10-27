import { StrictMode, useEffect, useState, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import "./product/auth.css";
import { Button, Field, PasswordField, Status } from "./ui";
import { AuthShell } from './product/AuthShell';

type State = "login" | "select_context" | "mfa" | "enroll" | "invite" | "reset" | "recover" | "session";
type LoginContext = { id: string; name: string; role: string };
type Result = { state?: State; secret?: string; recovery_codes?: string[]; message?: string; email?: string; role?: string; destination?: 'platform' | 'tenant'; contexts?: LoginContext[] };

async function request(path: string, body: object, area: 'auth' | 'shared' | 'platform/auth' = 'auth'): Promise<Result> {
  const csrf = await fetch("/api/v1/auth/csrf", { credentials: "same-origin" });
  if (!csrf.ok) throw new Error("The secure request could not be started. Refresh and try again.");
  let csrfToken = '';
  try { csrfToken = ((await csrf.json()) as { csrf_token?: string }).csrf_token || ''; }
  catch { throw new Error("The secure request could not be started. Refresh and try again."); }
  if (!csrfToken) throw new Error("The secure request could not be started. Refresh and try again.");
  const response = await fetch(`/api/v1/${area}/${path}`, {
    method: "POST", credentials: "same-origin",
    headers: { "content-type": "application/json", "x-csrf-token": csrfToken },
    body: JSON.stringify(body),
  });
  let result: Result & { detail?: { message?: string } } = {};
  try { result = await response.json() as Result & { detail?: { message?: string } }; }
  catch { if (response.ok) throw new Error('The service returned an unreadable response. Try again.'); }
  if (!response.ok) {
    const serverMessage = result.detail?.message || '';
    if (response.status === 429 || /too many|locked|rate limit/i.test(serverMessage)) throw new Error('Too many attempts were made. Wait a moment, then try again or reset your password.');
    if (response.status === 401) throw new Error('The credentials or verification code were not accepted. Check them and try again.');
    if (response.status === 403) throw new Error('This account does not have access to the requested workspace.');
    if (response.status >= 500) throw new Error('The sign-in service is temporarily unavailable. Try again shortly.');
    throw new Error('The request could not be completed. Review the information and try again.');
  }
  return result;
}

function App() {
  const initial: State = location.pathname === "/invite" ? "invite" : location.pathname === "/reset" ? "reset" : "login";
  const [linkToken] = useState(() => new URLSearchParams(location.hash.slice(1)).get("token"));
  const [linkTenant] = useState(() => new URLSearchParams(location.hash.slice(1)).get("tenant"));
  const [state, setState] = useState<State>(initial);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [secret, setSecret] = useState("");
  const [codes, setCodes] = useState<string[]>([]);
  const [recovery, setRecovery] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [tenantHost, setTenantHost] = useState("");
  const [role, setRole] = useState("");
  const [sharedHost, setSharedHost] = useState<boolean | null>(null);
  const [destination, setDestination] = useState<'platform' | 'tenant'>('tenant');
  const [contexts, setContexts] = useState<LoginContext[]>([]);

  async function loadSessionRole(target: 'platform' | 'tenant' = destination) {
    if (target === 'platform') { setRole('platform_admin'); return true; }
    const response = await fetch("/api/v1/auth/session", { credentials: "same-origin" });
    if (!response.ok) return false;
    const current = await response.json() as { role?: string };
    setRole(current.role || "");
    return true;
  }

  useEffect(() => {
    if (initial === "invite" || initial === "reset") history.replaceState(null, "", location.pathname);
  }, [initial]);

  useEffect(() => { void fetch('/api/v1/shared/context', { credentials: 'same-origin' })
    .then(async response => setSharedHost(response.ok && (await response.json() as { shared: boolean }).shared))
    .catch(() => setSharedHost(false)); }, []);

  useEffect(() => {
    if (initial !== "login") return;
    fetch("/api/v1/auth/session", { credentials: "same-origin" }).then(async (response) => {
      if (response.ok) {
        const current = await response.json() as { role?: string }; setRole(current.role || "");
        sessionStorage.setItem("staff_session_seen", "1");
        setState("session");
      } else if (response.status !== 200 && sharedHost) {
        const platform = await fetch('/api/v1/platform/auth/session', { credentials: 'same-origin' });
        if (platform.ok) { setDestination('platform'); setRole('platform_admin'); setState('session'); return; }
      }
      if (response.status === 401 && sessionStorage.getItem("staff_session_seen")) {
        sessionStorage.removeItem("staff_session_seen");
        setMessage("Your session has expired. Sign in again.");
      }
    }).catch(() => undefined);
  }, [initial, sharedHost]);
  const titles: Record<State, string> = {
    login: "Staff sign in", select_context: "Choose your workspace", mfa: "Verify your identity", enroll: "Set up an authenticator",
    invite: "Accept invitation", reset: "Choose a new password", recover: "Reset your password",
    session: "Signed in",
  };

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError(""); setMessage("");
    try {
      let result: Result;
      if (state === "login") {
        const shared = sharedHost ?? await fetch('/api/v1/shared/context', { credentials: 'same-origin' })
          .then(async response => response.ok && (await response.json() as { shared: boolean }).shared)
          .catch(() => false);
        result = await request("login", { email, password }, shared ? 'shared' : 'auth');
      }
      else if (state === "invite") result = await request("invitations/accept", { token: linkToken, password, tenant_id: linkTenant });
      else if (state === "reset") {
        await request("password-reset/complete", { token: linkToken, password, tenant_id: linkTenant });
        result = { state: "login", message: "Password updated. Sign in again." };
      } else if (state === "recover") {
        const shared = sharedHost ?? await fetch('/api/v1/shared/context', { credentials: 'same-origin' })
          .then(async response => response.ok && (await response.json() as { shared: boolean }).shared)
          .catch(() => false);
        result = await request("password-reset/request", { email }, shared ? 'shared' : 'auth');
      }
      else result = await request("mfa/verify", { code, recovery }, destination === 'platform' ? 'platform/auth' : 'auth');
      if (result.state) setState(result.state);
      if (result.destination) setDestination(result.destination);
      if (result.contexts) setContexts(result.contexts);
      if (result.state === "session") { sessionStorage.setItem("staff_session_seen", "1"); await loadSessionRole(result.destination || destination); }
      setMessage(result.message || ""); setCodes(result.recovery_codes || []);
      if (result.state !== 'select_context') setPassword(""); setCode("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Request failed"); }
    finally { setBusy(false); }
  }

  async function chooseContext(contextId: string) {
    if (busy) return;
    setBusy(true); setError('');
    try {
      const result = await request('login', { email, password, context: contextId }, 'shared');
      setDestination(result.destination || 'tenant');
      setState(result.state || 'login');
      if (result.state === 'session') {
        sessionStorage.setItem('staff_session_seen', '1');
        await loadSessionRole(result.destination || 'tenant');
      }
      setPassword('');
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Sign in failed'); }
    finally { setBusy(false); }
  }

  async function enroll() {
    setBusy(true); setError("");
    try { setSecret((await request("mfa/enroll", {}, destination === 'platform' ? 'platform/auth' : 'auth')).secret || ""); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Enrollment failed"); }
    finally { setBusy(false); }
  }

  async function logout() {
    setBusy(true); setError("");
    try { await request("logout", {}, destination === 'platform' ? 'platform/auth' : 'auth'); sessionStorage.removeItem("staff_session_seen"); setState("login"); setCodes([]); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Logout failed"); }
    finally { setBusy(false); }
  }

  function switchTenant() {
    const host = tenantHost.trim().toLowerCase();
    if (!/^[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$/.test(host) || !host.includes(".")) {
      setError("Enter a valid organization domain.");
      return;
    }
    location.assign(`${location.protocol}//${host}${location.port ? `:${location.port}` : ""}/`);
  }

  const descriptions: Record<State,string> = {
    login: 'Use your staff credentials to access your authorized workspace.', select_context: 'Choose one of the workspaces linked to your verified account.', mfa: 'Enter the current code from your authenticator.',
    enroll: 'Add the setup key to an authenticator, then enter its six-digit code.', invite: 'Set a strong password to activate your invitation.',
    reset: 'Choose a new password for this organization.', recover: 'We will send a neutral recovery response to the address provided.',
    session: 'Your secure organization session is active.',
  };

  return <AuthShell area="Organizer access" title={titles[state]} description={descriptions[state]}><section aria-labelledby="auth-title">
    {error && <Status tone="danger" title={error.startsWith('Too many attempts') ? 'Sign-in temporarily limited' : 'Could not continue'} instruction={error} announce="assertive" />}
    {message && <Status tone="info" title="Update" instruction={message} announce="polite" />}
    {state === "session" ? <div className="stack">
      {codes.length > 0 && <div><h2>Save recovery codes</h2><p>Each code works once. Store them safely.</p><pre className="recovery-codes">{codes.join("\n")}</pre></div>}
      <a className="workspace-link" href={destination === 'platform' ? '/platform-console.html' : ['gate_scanner','gate_staff','gate_supervisor'].includes(role) ? '/gate.html' : '/workspace.html'}>{destination === 'platform' ? 'Open Platform Console' : ['gate_scanner','gate_staff','gate_supervisor'].includes(role) ? 'Open assigned gate' : 'Open organizer workspace'}</a>
      <Button variant="secondary" onClick={logout} loading={busy} loadingText="Signing out…">Sign out</Button>
      {!sharedHost && <div className="tenant-switch"><Field label="Another organization’s domain" type="text" inputMode="url" autoComplete="off" value={tenantHost} onChange={(e) => setTenantHost(e.target.value)} /><Button variant="secondary" onClick={switchTenant}>Open organization</Button></div>}
    </div> : <form onSubmit={submit} className="stack">
      {state === 'select_context' && <div className="stack" role="group" aria-label="Available workspaces">{contexts.map(context => <Button key={context.id} variant="secondary" loading={busy} onClick={() => void chooseContext(context.id)}>{context.name} · {context.role.replaceAll('_',' ')}</Button>)}</div>}
      {(state === "login" || state === "recover") && <Field label="Email address" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />}
      {(state === "login" || state === "invite" || state === "reset") && <PasswordField label="Password" autoComplete={state === "login" ? "current-password" : "new-password"} required minLength={state === "login" ? undefined : 12} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} />}
      {state === "enroll" && <><Button variant="secondary" onClick={enroll} loading={busy} loadingText="Generating setup key…">Generate setup key</Button>{secret && <p className="key">Setup key: <code>{secret}</code></p>}</>}
      {(state === "mfa" || state === "enroll") && <><Field label={recovery ? "Recovery code" : "Six-digit code"} inputMode={recovery ? "text" : "numeric"} autoComplete="one-time-code" required value={code} onChange={(e) => setCode(e.target.value)} />{state === "mfa" && <Button variant="tertiary" onClick={() => setRecovery(!recovery)}>{recovery ? "Use authenticator code" : "Use a recovery code"}</Button>}</>}
      {state !== 'select_context' && <Button type="submit" loading={busy} loadingText="Working…" disabled={state === "enroll" && !secret}>{state === "login" ? "Sign in" : state === "recover" ? "Send reset link" : state === "invite" ? "Accept invitation" : state === "reset" ? "Update password" : "Verify code"}</Button>}
      {state === "login" && <Button variant="tertiary" onClick={() => setState("recover")}>Forgot password?</Button>}
      {state === "recover" && <Button variant="tertiary" onClick={() => setState("login")}>Back to sign in</Button>}
    </form>}
    <p className="footnote">Access is determined by your verified account and server-side assignments.</p>
  </section></AuthShell>;
}

const root = document.getElementById("root");
if (!root) throw new Error("Missing root element");
createRoot(root).render(<StrictMode><App /></StrictMode>);

