export type Theme = 'light' | 'dark';

const key = 'event-checkin-theme';

export function getTheme(): Theme {
  try {
    return localStorage.getItem(key) === 'dark' ? 'dark' : 'light';
  } catch {
    return 'light';
  }
}

export function setTheme(theme: Theme): void {
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem(key, theme); } catch { /* storage may be disabled */ }
}

export function initializeTheme(): Theme {
  const theme = getTheme();
  document.documentElement.dataset.theme = theme;
  return theme;
}
