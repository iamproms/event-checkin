import { useId, type ButtonHTMLAttributes, type ReactNode } from 'react';

export type ButtonVariant = 'primary' | 'secondary' | 'tertiary' | 'destructive';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  loading?: boolean;
  loadingText?: string;
  touchCritical?: boolean;
  disabledReason?: string;
  children: ReactNode;
}

export function Button({
  variant = 'primary', loading = false, loadingText, touchCritical = false, disabledReason,
  disabled, type = 'button', className = '', children, onClick, ...props
}: ButtonProps) {
  const generatedId = useId();
  const reasonId = `${props.id || generatedId}-disabled-reason`;
  const label = loading ? (loadingText ?? (typeof children === 'string' ? `${children}…` : 'Working…')) : children;
  return <span className="ui-button-wrap">
    <button
      {...props}
      type={type}
      disabled={disabled}
      aria-disabled={loading || undefined}
      aria-busy={loading || undefined}
      aria-describedby={disabled && disabledReason ? reasonId : props['aria-describedby']}
      onClick={(event) => {
        if (loading) {
          event.preventDefault();
          event.stopPropagation();
          return;
        }
        onClick?.(event);
      }}
      className={`ui-button ui-button--${variant}${touchCritical ? ' ui-button--touch' : ''} ${className}`.trim()}
    >{loading && <span className="ui-spinner" aria-hidden="true" />}{label}</button>
    {disabled && disabledReason && <span className="ui-control-note" id={reasonId}>{disabledReason}</span>}
  </span>;
}
