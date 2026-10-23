import { useId, type InputHTMLAttributes } from 'react';

export interface FieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'children'> {
  label: string;
  hint?: string;
  error?: string;
}

export function Field({ label, hint, error, id, className = '', 'aria-describedby': describedBy, ...input }: FieldProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const description = [describedBy, hintId, errorId].filter(Boolean).join(' ') || undefined;
  return <div className={`ui-field ${className}`.trim()}>
    <label className="ui-field__label" htmlFor={inputId}>{label}</label>
    <input {...input} id={inputId} className="ui-field__input" aria-invalid={error ? true : undefined} aria-describedby={description} />
    {hint && <p className="ui-field__hint" id={hintId}>{hint}</p>}
    {error && <p className="ui-field__error" id={errorId} role="alert">{error}</p>}
  </div>;
}
