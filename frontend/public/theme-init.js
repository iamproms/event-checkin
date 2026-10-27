(function () {
  try {
    var stored = localStorage.getItem('event-checkin-theme');
    var preference = stored === 'light' || stored === 'dark' ? stored : 'system';
    document.documentElement.dataset.themePreference = preference;
    document.documentElement.dataset.theme = preference === 'system'
      ? (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
      : preference;
  } catch {
    document.documentElement.dataset.themePreference = 'system';
    document.documentElement.dataset.theme = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
})();
