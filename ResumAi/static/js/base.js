document.addEventListener('DOMContentLoaded', () => {
    const html = document.documentElement;
    const toggle = document.getElementById('themeToggle');
    const icon = document.getElementById('themeIcon');
    const navMenuToggle = document.getElementById('navMenuToggle');
    const navLinks = document.getElementById('navLinks');

    const storedTheme = localStorage.getItem('theme');
    const savedTheme = storedTheme === 'pink' || storedTheme === 'blue' ? storedTheme : 'blue';
    html.setAttribute('data-theme', savedTheme);
    icon.className = savedTheme === 'pink' ? 'fas fa-gem' : 'fas fa-droplet';

    if (toggle) {
        toggle.addEventListener('click', () => {
            const current = html.getAttribute('data-theme');
            const next = current === 'blue' ? 'pink' : 'blue';
            html.setAttribute('data-theme', next);
            icon.className = next === 'pink' ? 'fas fa-gem' : 'fas fa-droplet';
            localStorage.setItem('theme', next);
        });
    }

    if (navMenuToggle && navLinks) {
        navMenuToggle.addEventListener('click', () => {
            const open = navLinks.classList.toggle('is-open');
            navMenuToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        });

        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                navLinks.classList.remove('is-open');
                navMenuToggle.setAttribute('aria-expanded', 'false');
            });
        });
    }
});
    
