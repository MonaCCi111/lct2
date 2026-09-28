// Blocking head script: shared by the pre-paint bootstrap and React provider.
(() => {
  const key = 'dolos-theme';
  const media = '(prefers-color-scheme: dark)';
  const read = () => {
    try {
      const value = localStorage.getItem(key);
      return value === 'light' || value === 'dark' ? value : 'system';
    } catch {
      return 'system';
    }
  };
  const resolve = (preference) =>
    preference === 'system' ? (matchMedia(media).matches ? 'dark' : 'light') : preference;
  const apply = (theme) => {
    document.documentElement.dataset.theme = theme;
  };
  const save = (preference) => {
    try {
      localStorage.setItem(key, preference);
    } catch {
      // Storage can be unavailable; the current session still supports theme changes.
    }
  };
  window.dolosTheme = { read, resolve, apply, save, media };
  apply(resolve(read()));
})();
