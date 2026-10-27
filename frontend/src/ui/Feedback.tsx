import type { ReactNode } from 'react';

export function InlineSpinner({ label = 'Working' }: { label?: string }) {
  return <span className="ui-inline-progress" role="status"><span className="ui-spinner" aria-hidden="true" /><span className="sr-only">{label}</span></span>;
}

export function Skeleton({ lines = 3, label = 'Loading content' }: { lines?: number; label?: string }) {
  return <div className="ui-skeleton" role="status" aria-label={label}>{Array.from({ length: lines }, (_, index) => <span key={index} />)}</div>;
}

export type ScreenStateTone = 'empty' | 'error' | 'soon' | 'restricted';

export function ScreenState({ tone, title, description, action, detail }: { tone: ScreenStateTone; title: string; description: string; action?: ReactNode; detail?: ReactNode }) {
  return <section className={`ui-screen-state ui-screen-state--${tone}`} role={tone === 'error' ? 'alert' : undefined}>
    <span className="ui-screen-state__mark" aria-hidden="true" />
    <div><h2>{title}</h2><p>{description}</p>{detail && <div className="ui-screen-state__detail">{detail}</div>}{action && <div className="ui-screen-state__action">{action}</div>}</div>
  </section>;
}
