(function() {
  const savedTheme = localStorage.getItem('urlguard-theme');
  const currentTheme = savedTheme ? savedTheme : 'light';
  
  if (currentTheme === 'light') {
    document.documentElement.classList.add('theme-light');
    document.documentElement.classList.remove('theme-dark');
    document.addEventListener('DOMContentLoaded', () => {
      document.body.classList.add('theme-light');
      document.body.classList.remove('theme-dark');
      initThemeUI();
    });
  } else {
    document.documentElement.classList.add('theme-dark');
    document.documentElement.classList.remove('theme-light');
    document.addEventListener('DOMContentLoaded', () => {
      document.body.classList.add('theme-dark');
      document.body.classList.remove('theme-light');
      initThemeUI();
    });
  }
  
  // Sync across tabs
  window.addEventListener('storage', (e) => {
    if (e.key === 'urlguard-theme') {
      applyTheme(e.newValue || 'light');
    }
  });

  function applyTheme(theme) {
    if (theme === 'light') {
      document.body.classList.add('theme-light');
      document.body.classList.remove('theme-dark');
      document.documentElement.classList.add('theme-light');
      document.documentElement.classList.remove('theme-dark');
    } else {
      document.body.classList.add('theme-dark');
      document.body.classList.remove('theme-light');
      document.documentElement.classList.add('theme-dark');
      document.documentElement.classList.remove('theme-light');
    }
    updateToggleIcons(theme);

    // Sync settings pill toggle on settings.html if present
    const settingsThemeToggle = document.querySelector('.settings-pill-toggle[data-setting-key="theme"]');
    if (settingsThemeToggle) {
      const buttons = settingsThemeToggle.querySelectorAll('button[data-value]');
      buttons.forEach(btn => {
        btn.classList.toggle('is-active', btn.getAttribute('data-value') === theme);
      });
    }
  }

  function updateToggleIcons(theme) {
    document.querySelectorAll('#themeToggle').forEach(btn => {
      const iconDark = btn.querySelector('.theme-icon-dark');
      const iconLight = btn.querySelector('.theme-icon-light');
      if (theme === 'light') {
        if (iconDark) iconDark.style.display = 'none';
        if (iconLight) iconLight.style.display = 'block';
      } else {
        if (iconDark) iconDark.style.display = 'block';
        if (iconLight) iconLight.style.display = 'none';
      }
    });
  }

  function initThemeUI() {
    setupToggleListeners();
    
    // Inject dynamic theme toggle button if .topbar-actions exists but no themeToggle
    const topbarActions = document.querySelector('.topbar-actions');
    if (topbarActions && !document.getElementById('themeToggle')) {
      const btn = document.createElement('button');
      btn.className = 'icon-button';
      btn.id = 'themeToggle';
      btn.type = 'button';
      btn.setAttribute('aria-label', 'Toggle theme');
      btn.innerHTML = `
        <svg class="theme-icon theme-icon-dark" viewBox="0 0 24 24" aria-hidden="true" style="width:20px;height:20px;"><path d="M18 15.6A7.7 7.7 0 0 1 8.4 6a8.8 8.8 0 1 0 9.6 9.6Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>
        <svg class="theme-icon theme-icon-light" viewBox="0 0 24 24" aria-hidden="true" style="width:20px;height:20px;"><path d="M12 3v2.2M12 18.8V21M4.9 4.9l1.6 1.6M17.5 17.5l1.6 1.6M3 12h2.2M18.8 12H21M4.9 19.1l1.6-1.6M17.5 6.5l1.6-1.6M15.4 12A3.4 3.4 0 1 1 8.6 12a3.4 3.4 0 0 1 6.8 0Z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>
      `;
      topbarActions.insertBefore(btn, topbarActions.firstChild);
      setupToggleListeners();
    }
    
    const savedTheme = localStorage.getItem('urlguard-theme');
    const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const currentTheme = savedTheme ? savedTheme : (systemPrefersDark ? 'dark' : 'light');
    updateToggleIcons(currentTheme);
  }

  function setupToggleListeners() {
    document.querySelectorAll('#themeToggle').forEach(btn => {
      if (btn.dataset.themeListenerAttached) return;
      btn.dataset.themeListenerAttached = 'true';
      btn.addEventListener('click', () => {
        const isLight = document.body.classList.contains('theme-light');
        const nextTheme = isLight ? 'dark' : 'light';
        localStorage.setItem('urlguard-theme', nextTheme);
        applyTheme(nextTheme);
      });
    });
  }
  
  window.ThemeManager = {
    applyTheme: applyTheme,
    getTheme: () => document.body.classList.contains('theme-light') ? 'light' : 'dark'
  };
})();
