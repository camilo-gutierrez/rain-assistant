// ---------------------------------------------------------------------------
// Theme Toggle (dark / light)
// ---------------------------------------------------------------------------

let themeToggle;

function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    themeToggle.textContent = theme === 'light' ? '\u2600\uFE0F' : '\uD83C\uDF19';
    localStorage.setItem('rain-theme', theme);
}

export function initTheme() {
    themeToggle = document.getElementById('theme-toggle');
    const saved = localStorage.getItem('rain-theme') || 'dark';
    setTheme(saved);

    themeToggle.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme');
        setTheme(current === 'light' ? 'dark' : 'light');
    });
}
