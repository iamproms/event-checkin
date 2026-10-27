import { useEffect, useState } from 'react';
import { getThemePreference, resolveTheme, setThemePreference, type Theme, type ThemePreference } from './theme';

export function ThemeControl({ compact = false }: { compact?: boolean }) {
  const [preference, updatePreference] = useState<ThemePreference>(getThemePreference);
  const [resolved, setResolved] = useState<Theme>(() => resolveTheme(preference));
  useEffect(() => {
    const media = matchMedia('(prefers-color-scheme: dark)');
    const sync = () => { if (getThemePreference() === 'system') { setThemePreference('system'); setResolved(resolveTheme('system')); } };
    media.addEventListener('change', sync);
    return () => media.removeEventListener('change', sync);
  }, []);
  function change(value: ThemePreference) { setThemePreference(value); updatePreference(value); setResolved(resolveTheme(value)); }
  const options: { value: ThemePreference; label: string }[] = [{ value: 'system', label: 'System' }, { value: 'light', label: 'Light' }, { value: 'dark', label: 'Dark' }];
  return <div className={`theme-control${compact ? ' theme-control--compact' : ''}`}>
    <span className={compact ? 'sr-only' : 'theme-control__label'}>Theme</span>
    <div className="theme-control__choices" role="group" aria-label="Theme preference">
      {options.map(option => <button key={option.value} type="button" aria-pressed={preference === option.value} aria-label={`Use ${option.label.toLowerCase()} theme`} title={compact ? option.label : undefined} onClick={() => change(option.value)}>{compact ? option.label.slice(0, 1) : <><span className="theme-control__full-label">{option.label}</span><span className="theme-control__short-label" aria-hidden="true">{option.label.slice(0, 1)}</span></>}</button>)}
    </div>
    {!compact && <span className="theme-control__resolved" aria-live="polite">Currently {resolved}</span>}
  </div>;
}
