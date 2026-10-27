import { useEffect, useState } from 'react';
import { getThemePreference, setThemePreference, type ThemePreference } from './theme';

export function ThemeControl({ compact = false }: { compact?: boolean }) {
  const [preference, updatePreference] = useState<ThemePreference>(getThemePreference);
  useEffect(() => {
    const media = matchMedia('(prefers-color-scheme: dark)');
    const sync = () => { if (getThemePreference() === 'system') setThemePreference('system'); };
    media.addEventListener('change', sync);
    return () => media.removeEventListener('change', sync);
  }, []);
  function change(value: ThemePreference) { setThemePreference(value); updatePreference(value); }
  return <label className={`theme-select${compact ? ' theme-select--compact' : ''}`}>
    <span className={compact ? 'sr-only' : undefined}>Theme</span>
    <select aria-label="Theme preference" value={preference} onChange={event => change(event.target.value as ThemePreference)}>
      <option value="system">{compact ? 'System' : 'System theme'}</option><option value="light">{compact ? 'Light' : 'Light theme'}</option><option value="dark">{compact ? 'Dark' : 'Dark theme'}</option>
    </select>
  </label>;
}
