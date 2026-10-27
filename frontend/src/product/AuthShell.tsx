import type { ReactNode } from 'react';
import { ThemeControl } from '../ui';

export function AuthShell({ area, title, description, children }: { area: string; title: string; description: string; children: ReactNode }) {
  return <main className="auth-shell">
    <section className="auth-scene" aria-label="Event operations preview">
      <div className="auth-scene-brand"><span className="auth-mark" aria-hidden="true">E</span><span>Event Check-in</span></div>
      <div className="venue-lines" aria-hidden="true"><span/><span/><span/><span/><span/></div>
      <div className="auth-scene-copy"><p>From registration to the gate</p><h2>One calm place to run every arrival.</h2><div className="arrival-strip"><span>Registration open</span><strong>1,284 expected</strong><span>12 Nov · Lagos</span></div></div>
    </section>
    <section className="auth-workspace">
      <div className="auth-utility"><span>{area}</span><ThemeControl compact /></div>
      <div className="auth-panel"><header><p className="auth-product">Event Check-in</p><h1 id="auth-title">{title}</h1><p>{description}</p></header>{children}</div>
      <footer>Secure, host-bound access · MFA for privileged roles</footer>
    </section>
  </main>;
}
