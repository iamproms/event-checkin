(function () {
  try {
    document.documentElement.dataset.theme = localStorage.getItem('event-checkin-theme') === 'dark' ? 'dark' : 'light';
  } catch {
    document.documentElement.dataset.theme = 'light';
  }
})();
