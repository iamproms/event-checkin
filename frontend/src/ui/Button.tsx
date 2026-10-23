import type { ButtonHTMLAttributes, ReactNode } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'tertiary' | 'destructive';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
  loadingText?: string;
  touchCritical?: boolean;
  children: ReactNode;
}

export function Button({
  variant = 'primary', loading = false, loadingText, touchCritical = false,
  disabled, type = 'button', className = '', children, onClick, ...props
}: ButtonProps) {
  const label = loading ? (loadingText ?? (typeof children === 'string' ? `${children}…` : 'Working…')) : children;
  return <button
    {...props}
    type={type}
    disabled={disabled}
    aria-disabled={loading || undefined}
    aria-busy={loading || undefined}
    onClick={(event) => {
      if (loading) {
        event.preventDefault();
        event.stopPropagation();
        return;
      }
      onClick?.(event);
    }}
    className={`ui-button ui-button--${variant}${touchCritical ? ' ui-button--touch' : ''} ${className}`.trim()}
  >{label}</button>;
}
