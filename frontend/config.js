// IT School — Frontend configuration
//
// Для локального запуску: API_BASE автоматично буде http://localhost:8000.
// Для Render-публікації: якщо сайт відкритий на *.onrender.com, frontend автоматично
// звертається до backend-сервісу https://it-school-backend.onrender.com.
//
// Якщо на Render ти назвеш backend інакше, зміни лише рядок RENDER_BACKEND_URL нижче.
// Наприклад: const RENDER_BACKEND_URL = 'https://my-school-api.onrender.com';

const __cfg = (typeof window !== 'undefined' && window.__APP_CONFIG__) || {};

const DEMO_MODE = (typeof __cfg.DEMO_MODE === 'boolean') ? __cfg.DEMO_MODE : false;

const LOCAL_API_BASE = 'http://localhost:8000';
const RENDER_BACKEND_URL = 'https://it-school-backend.onrender.com';

function detectApiBase() {
    if (typeof __cfg.API_BASE === 'string' && __cfg.API_BASE.trim()) {
        return __cfg.API_BASE.trim().replace(/\/$/, '');
    }

    if (typeof window === 'undefined') {
        return LOCAL_API_BASE;
    }

    const host = window.location.hostname;
    const isLocal = host === 'localhost' || host === '127.0.0.1' || host === '';

    if (isLocal) {
        return LOCAL_API_BASE;
    }

    // Render Static Site / production hosting
    if (host.endsWith('.onrender.com')) {
        return RENDER_BACKEND_URL;
    }

    // Якщо сайт відкритий з іншого хостингу, можна передати window.__APP_CONFIG__.API_BASE
    // або тимчасово використовувати Render backend URL.
    return RENDER_BACKEND_URL;
}

const API_BASE = detectApiBase();
