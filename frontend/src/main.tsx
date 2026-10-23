import { StrictMode, useEffect, useState, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

type State = "login" | "mfa" | "enroll" | "invite" | "reset" | "recover" | "session";
type Result = { state?: State; secret?: string; recovery_codes?: string[]; message?: string; email?: string };

async function request(path: string, body: object): Promise<Result> {
  const csrf = await fetch("/api/v1/auth/csrf", { credentials: "same-origin" });
  if (!csrf.ok) throw new Error("Request verification failed");
  const { csrf_token } = await csrf.json() as { csrf_token: string };
  const response = await fetch(`/api/v1/auth/${path}`, {
    method: "POST", credentials: "same-origin",
    headers: { "content-type": "application/json", "x-csrf-token": csrf_token },
    body: JSON.stringify(body),
  });
  const result = await response.json() as Result & { detail?: { message?: string } };
  if (!response.ok) throw new Error(result.detail?.message || "Request failed");
  return result;
}

function App() {
  const initial: State = location.pathname === "/invite" ? "invite" : location.pathname === "/reset" ? "reset" : "login";
  const [linkToken] = useState(() => new URLSearchParams(location.hash.slice(1)).get("token"));
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

  useEffect(() => {
    if (initial === "invite" || initial === "reset") history.replaceState(null, "", location.pathname);
  }, [initial]);

  useEffect(() => {
    if (initial !== "login") return;
    fetch("/api/v1/auth/session", { credentials: "same-origin" }).then((response) => {
      if (response.ok) {
        sessionStorage.setItem("staff_session_seen", "1");
        setState("session");
      } else if (response.status === 401 && sessionStorage.getItem("staff_session_seen")) {
        sessionStorage.removeItem("staff_session_seen");
        setMessage("Your session has expired. Sign in again.");
      }
    }).catch(() => undefined);
  }, [initial]);
  const titles: Record<State, string> = {
    login: "Staff sign in", mfa: "Verify your identity", enroll: "Set up an authenticator",
    invite: "Accept invitation", reset: "Choose a new password", recover: "Reset your password",
    session: "Signed in",
  };

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      let result: Result;
      if (state === "login") result = await request("login", { email, password });
      else if (state === "invite") result = await request("invitations/accept", { token: linkToken, password });
      else if (state === "reset") {
        await request("password-reset/complete", { token: linkToken, password });
        result = { state: "login", message: "Password updated. Sign in again." };
      } else if (state === "recover") result = await request("password-reset/request", { email });
      else result = await request("mfa/verify", { code, recovery });
      if (result.state) setState(result.state);
      if (result.state === "session") sessionStorage.setItem("staff_session_seen", "1");
      setMessage(result.message || ""); setCodes(result.recovery_codes || []);
      setPassword(""); setCode("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Request failed"); }
    finally { setBusy(false); }
  }

  async function enroll() {
    setBusy(true); setError("");
    try { setSecret((await request("mfa/enroll", {})).secret || ""); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Enrollment failed"); }
    finally { setBusy(false); }
  }

  async function logout() {
    setBusy(true); setError("");
    try { await request("logout", {}); sessionStorage.removeItem("staff_session_seen"); setState("login"); setCodes([]); }
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

  return <main className="page"><section className="panel" aria-labelledby="title">
    <p className="brand">Event Check-in</p><h1 id="title">{titles[state]}</h1>
    {state === "login" && <p className="intro">Use your staff credentials for this organization.</p>}
    {state === "enroll" && <p className="intro">Add the setup key to an authenticator, then enter its six-digit code.</p>}
    {error && <p role="alert" className="notice error">{error}</p>}
    {message && <p role="status" className="notice">{message}</p>}
    {state === "session" ? <div className="stack">
      {codes.length > 0 && <div><h2>Save recovery codes</h2><p>Each code works once. Store them safely.</p><pre>{codes.join("\n")}</pre></div>}
      <button className="secondary" onClick={logout} disabled={busy}>Sign out</button>
      <div className="tenant-switch"><label>Another organization’s domain<input type="text" inputMode="url" autoComplete="off" value={tenantHost} onChange={(e) => setTenantHost(e.target.value)} /></label><button className="secondary" type="button" onClick={switchTenant}>Open organization</button></div>
    </div> : <form onSubmit={submit} className="stack">
      {(state === "login" || state === "recover") && <label>Email address<input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>}
      {(state === "login" || state === "invite" || state === "reset") && <label>Password<input type="password" autoComplete={state === "login" ? "current-password" : "new-password"} required minLength={state === "login" ? undefined : 12} maxLength={128} value={password} onChange={(e) => setPassword(e.target.value)} /></label>}
      {state === "enroll" && <><button className="secondary" type="button" onClick={enroll} disabled={busy}>Generate setup key</button>{secret && <p className="key">Setup key: <code>{secret}</code></p>}</>}
      {(state === "mfa" || state === "enroll") && <><label>{recovery ? "Recovery code" : "Six-digit code"}<input inputMode={recovery ? "text" : "numeric"} autoComplete="one-time-code" required value={code} onChange={(e) => setCode(e.target.value)} /></label>{state === "mfa" && <button className="text-button" type="button" onClick={() => setRecovery(!recovery)}>{recovery ? "Use authenticator code" : "Use a recovery code"}</button>}</>}
      <button type="submit" disabled={busy || (state === "enroll" && !secret)}>{busy ? "Working…" : state === "login" ? "Sign in" : state === "recover" ? "Send reset link" : state === "invite" ? "Accept invitation" : state === "reset" ? "Update password" : "Verify code"}</button>
      {state === "login" && <button type="button" className="text-button" onClick={() => setState("recover")}>Forgot password?</button>}
      {state === "recover" && <button type="button" className="text-button" onClick={() => setState("login")}>Back to sign in</button>}
    </form>}
    <p className="footnote">To use another organization, open its verified domain and sign in there.</p>
  </section></main>;
}

const root = document.getElementById("root");
if (!root) throw new Error("Missing root element");
createRoot(root).render(<StrictMode><App /></StrictMode>);

