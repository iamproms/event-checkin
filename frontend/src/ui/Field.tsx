import { useId, useState, type InputHTMLAttributes, type SelectHTMLAttributes, type TextareaHTMLAttributes } from 'react';

export interface FieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'children'> {
  label: string;
  hint?: string;
  error?: string;
}

export interface PasswordFieldProps extends Omit<FieldProps, 'type'> {
  showLabel?: string;
  hideLabel?: string;
}

export function PasswordField({ showLabel = 'Show password', hideLabel = 'Hide password', ...props }: PasswordFieldProps) {
  const [visible, setVisible] = useState(false);
  const generatedId = useId();
  const inputId = props.id ?? generatedId;
  const hintId = props.hint ? `${inputId}-hint` : undefined;
  const errorId = props.error ? `${inputId}-error` : undefined;
  const { label, hint, error, className = '', 'aria-describedby': describedBy, ...input } = props;
  const description = [describedBy, hintId, errorId].filter(Boolean).join(' ') || undefined;
  return <div className={`ui-field ${className}`.trim()}>
    <label className="ui-field__label" htmlFor={inputId}>{label}</label>
    <div className="ui-password">
      <input {...input} id={inputId} type={visible ? 'text' : 'password'} className="ui-field__input" aria-invalid={error ? true : undefined} aria-describedby={description} />
      <button type="button" className="ui-password__toggle" aria-pressed={visible} aria-label={visible ? hideLabel : showLabel} onClick={() => setVisible(value => !value)}>{visible ? 'Hide' : 'Show'}</button>
    </div>
    {hint && <p className="ui-field__hint" id={hintId}>{hint}</p>}
    {error && <p className="ui-field__error" id={errorId} role="alert">{error}</p>}
  </div>;
}

export interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  hint?: string;
  error?: string;
}

export function SelectField({ label, hint, error, id, className = '', children, ...select }: SelectFieldProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  return <div className={`ui-field ${className}`.trim()}>
    <label className="ui-field__label" htmlFor={inputId}>{label}</label>
    <select {...select} id={inputId} className="ui-field__input" aria-invalid={error ? true : undefined}>{children}</select>
    {hint && <p className="ui-field__hint">{hint}</p>}
    {error && <p className="ui-field__error" role="alert">{error}</p>}
  </div>;
}

export interface TextareaFieldProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
  hint?: string;
  error?: string;
}

export function TextareaField({ label, hint, error, id, className = '', ...textarea }: TextareaFieldProps) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  return <div className={`ui-field ${className}`.trim()}>
    <label className="ui-field__label" htmlFor={inputId}>{label}</label>
    <textarea {...textarea} id={inputId} className="ui-field__input ui-field__textarea" aria-invalid={error ? true : undefined} />
    {hint && <p className="ui-field__hint">{hint}</p>}
    {error && <p className="ui-field__error" role="alert">{error}</p>}
  </div>;
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
