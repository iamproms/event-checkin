import type { ReactNode } from 'react';

export type StatusTone = 'success' | 'warning' | 'danger' | 'info';

export interface StatusProps {
  tone: StatusTone;
  title: string;
  instruction: ReactNode;
  announce?: 'polite' | 'assertive' | false;
  className?: string;
}

export function Status({ tone, title, instruction, announce = false, className = '' }: StatusProps) {
  return <div
    className={`ui-status ui-status--${tone} ${className}`.trim()}
    role={announce === 'assertive' ? 'alert' : announce === 'polite' ? 'status' : undefined}
  >
    <strong className="ui-status__title">{title}</strong>
    <div className="ui-status__instruction">{instruction}</div>
  </div>;
}
