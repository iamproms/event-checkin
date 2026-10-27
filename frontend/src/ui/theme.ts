export type Theme = 'light' | 'dark';
export type ThemePreference = 'system' | Theme;

const key = 'event-checkin-theme';

export function getThemePreference(): ThemePreference {
  try {
    const value = localStorage.getItem(key);
    return value === 'light' || value === 'dark' ? value : 'system';
  } catch {
    return 'system';
  }
}

export function resolveTheme(preference = getThemePreference()): Theme {
  if (preference !== 'system') return preference;
  return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function getTheme(): Theme { return resolveTheme(); }

export function setTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  document.documentElement.dataset.themePreference = theme;
  try { localStorage.setItem(key, theme); } catch { /* storage may be disabled */ }
}

export function setThemePreference(preference: ThemePreference): void {
  document.documentElement.dataset.themePreference = preference;
  document.documentElement.dataset.theme = resolveTheme(preference);
  try {
    if (preference === 'system') localStorage.removeItem(key);
    else localStorage.setItem(key, preference);
  } catch { /* storage may be disabled */ }
}

export function initializeTheme(): Theme {
  const preference = getThemePreference();
  const theme = resolveTheme(preference);
  document.documentElement.dataset.themePreference = preference;
  document.documentElement.dataset.theme = theme;
  return theme;
}
