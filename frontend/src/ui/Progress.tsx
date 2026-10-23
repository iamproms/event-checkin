import { useId } from 'react';

export interface ProgressProps {
  label: string;
  value?: number;
  max?: number;
  className?: string;
}

export function Progress({ label, value, max = 100, className = '' }: ProgressProps) {
  const id = useId();
  const safeMax = Number.isFinite(max) && max > 0 ? max : 100;
  const boundedValue = value === undefined || !Number.isFinite(value) ? undefined : Math.min(safeMax, Math.max(0, value));
  const percentage = boundedValue === undefined ? undefined : Math.round((boundedValue / safeMax) * 100);
  return <div className={`ui-progress ${className}`.trim()}>
    <div className="ui-progress__head"><label htmlFor={id}>{label}</label><span>{percentage === undefined ? 'In progress' : `${percentage}%`}</span></div>
    <progress id={id} max={safeMax} value={boundedValue} />
  </div>;
}
