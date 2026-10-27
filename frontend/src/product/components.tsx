import type { ReactNode } from 'react';
import { Icon, type IconName } from './icons';
import type { Capability } from './capabilities';

export function CapabilityTag({ capability }: { capability: Capability }) {
  return <span className={`capability capability--${capability.mode}`}><span aria-hidden="true" />{capability.label}</span>;
}

export function CapabilityNotice({ capability, children }: { capability: Capability; children?: ReactNode }) {
  return <aside className={`capability-notice capability-notice--${capability.mode}`}>
    <div><CapabilityTag capability={capability} /><strong>{capability.mode === 'live' ? 'Connected workflow' : capability.mode === 'demo' ? 'Preview environment' : 'Backend required'}</strong></div>
    <p>{children || capability.explanation}</p>
  </aside>;
}

export function PageHeader({ eyebrow, title, description, actions }: { eyebrow?: string; title: string; description: string; actions?: ReactNode }) {
  return <header className="page-header"><div>{eyebrow && <p className="context-label">{eyebrow}</p>}<h1>{title}</h1><p>{description}</p></div>{actions && <div className="page-actions">{actions}</div>}</header>;
}

export function ButtonLink({ href, children, secondary = false }: { href: string; children: ReactNode; secondary?: boolean }) {
  return <a className={`product-button${secondary ? ' product-button--secondary' : ''}`} href={href}>{children}</a>;
}

export type Metric = { label: string; value: string; detail: string };
export function MetricStrip({ metrics }: { metrics: Metric[] }) {
  return <section className="metric-strip" aria-label="Summary metrics">{metrics.map((metric) => <div key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong><small>{metric.detail}</small></div>)}</section>;
}

export function SectionHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return <div className="section-header"><div><h2>{title}</h2>{description && <p>{description}</p>}</div>{action}</div>;
}

export function TrendChart({ label, values, secondary }: { label: string; values: number[]; secondary?: number[] }) {
  const width = 640, height = 190, max = Math.max(...values, ...(secondary || []), 1);
  const points = (series: number[]) => series.map((value, index) => `${(index / (series.length - 1)) * width},${height - (value / max) * (height - 24)}`).join(' ');
  return <div className="chart" role="img" aria-label={label}><svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none"><path className="chart-grid" d="M0 32h640M0 84h640M0 136h640M0 188h640" />{secondary && <polyline className="chart-line chart-line--secondary" points={points(secondary)} />}<polyline className="chart-line" points={points(values)} /></svg><div className="chart-axis"><span>08 Oct</span><span>14 Oct</span><span>20 Oct</span><span>26 Oct</span></div></div>;
}

export function DataTable({ columns, rows, label }: { columns: string[]; rows: ReactNode[][]; label: string }) {
  return <div className="table-wrap"><table><caption className="sr-only">{label}</caption><thead><tr>{columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr></thead><tbody>{rows.map((row, rowIndex) => <tr key={rowIndex}>{row.map((cell, columnIndex) => <td key={columnIndex} data-label={columns[columnIndex]}>{cell}</td>)}</tr>)}</tbody></table></div>;
}

export function StatusMark({ tone, children }: { tone: 'success' | 'warning' | 'danger' | 'neutral' | 'info'; children: ReactNode }) {
  return <span className={`status-mark status-mark--${tone}`}><span aria-hidden="true" />{children}</span>;
}

export function EmptyState({ icon, title, description, action }: { icon: IconName; title: string; description: string; action?: ReactNode }) {
  return <div className="empty-state"><Icon name={icon} /><h2>{title}</h2><p>{description}</p>{action}</div>;
}

export function FilterBar({ placeholder = 'Search', count, children, value, onChange }: { placeholder?: string; count?: string; children?: ReactNode; value?: string; onChange?: (value: string) => void }) {
  return <div className="filter-bar"><label className="search-field"><span className="sr-only">{placeholder}</span><Icon name="search" /><input type="search" placeholder={placeholder} value={value} onChange={event => onChange?.(event.target.value)} /></label><div>{count && <span className="filter-count">{count}</span>}{children}</div></div>;
}

export function Timeline({ items }: { items: { time: string; title: string; detail: string; tone?: string }[] }) {
  return <ol className="timeline">{items.map((item) => <li key={`${item.time}-${item.title}`} className={item.tone ? `timeline--${item.tone}` : ''}><time>{item.time}</time><div><strong>{item.title}</strong><p>{item.detail}</p></div></li>)}</ol>;
}

export function SettingRow({ title, description, children }: { title: string; description: string; children: ReactNode }) {
  return <section className="setting-row"><div><h2>{title}</h2><p>{description}</p></div><div className="setting-panel">{children}</div></section>;
}
