// ---------------------------------------------------------------------------
// Theme management (dark / light / ocean)
// ---------------------------------------------------------------------------

const THEMES = ['dark', 'light', 'ocean'];

export function getTheme() {
    return localStorage.getItem('rain-theme') || 'dark';
}

export function setTheme(theme) {
    if (!THEMES.includes(theme)) theme = 'dark';
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('rain-theme', theme);

    // Update active state on theme buttons in settings (if panel exists)
    document.querySelectorAll('.theme-option').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.themeValue === theme);
    });
}

export function initTheme() {
    const saved = getTheme();
    setTheme(saved);
}
