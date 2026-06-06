// DOM Elements
const header = document.getElementById('header');
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
const loginForm = document.getElementById('loginForm');
const passwordToggle = document.getElementById('passwordToggle');
const passwordInput = document.getElementById('password');
const emailInput = document.getElementById('email');
const errorMessage = document.getElementById('errorMessage');
const errorText = document.getElementById('errorText');

// Mobile Menu
function createMobileMenu() {
    const mobileMenu = document.createElement('div');
    mobileMenu.className = 'mobile-menu';
    mobileMenu.innerHTML = `
        <div class="mobile-menu-content">
            <button class="mobile-menu-close">&times;</button>
            <div class="logo">
                <div class="logo-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
                        <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
                    </svg>
                </div>
                <span>IT School</span>
            </div>
            <nav class="mobile-menu-nav">
                <a href="#home" class="nav-link">Головна</a>
                <a href="#login" class="btn btn-primary">Увійти</a>
            </nav>
        </div>
    `;
    
    document.body.appendChild(mobileMenu);
    
    const closeBtn = mobileMenu.querySelector('.mobile-menu-close');
    const navLinks = mobileMenu.querySelectorAll('.nav-link, .btn');
    
    closeBtn.addEventListener('click', closeMobileMenu);
    navLinks.forEach(link => {
        link.addEventListener('click', closeMobileMenu);
    });
    
    mobileMenu.addEventListener('click', (e) => {
        if (e.target === mobileMenu) {
            closeMobileMenu();
        }
    });
    
    return mobileMenu;
}

// Mobile menu only exists on the landing page (where mobileMenuBtn is present).
let mobileMenu = null;
if (mobileMenuBtn) {
    mobileMenu = createMobileMenu();
}

function openMobileMenu() {
    if (!mobileMenu) return;
    mobileMenu.classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeMobileMenu() {
    if (!mobileMenu) return;
    mobileMenu.classList.remove('active');
    document.body.style.overflow = '';
}

if (mobileMenuBtn) mobileMenuBtn.addEventListener('click', openMobileMenu);

// Header scroll effect
function updateHeader() {
    if (!header) return;
    if (window.scrollY > 50) {
        header.classList.add('scrolled');
    } else {
        header.classList.remove('scrolled');
    }
}

window.addEventListener('scroll', updateHeader);

// Smooth scrolling
function scrollToFeatures() {
    const featuresSection = document.getElementById('features');
    if (featuresSection) {
        featuresSection.scrollIntoView({ 
            behavior: 'smooth',
            block: 'start'
        });
    }
}

// Navigation active state
function updateActiveNav() {
    const sections = document.querySelectorAll('section[id]');
    const navLinks = document.querySelectorAll('.nav-link');
    
    let currentSection = '';
    
    sections.forEach(section => {
        const rect = section.getBoundingClientRect();
        if (rect.top <= 100 && rect.bottom >= 100) {
            currentSection = section.getAttribute('id');
        }
    });
    
    navLinks.forEach(link => {
        link.classList.remove('active');
        if (link.getAttribute('href') === `#${currentSection}`) {
            link.classList.add('active');
        }
    });
}

window.addEventListener('scroll', updateActiveNav);

// Password toggle
if (passwordToggle && passwordInput) passwordToggle.addEventListener('click', () => {
    const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
    passwordInput.setAttribute('type', type);
    
    const eyeOpen = passwordToggle.querySelector('.eye-open');
    const eyeClosed = passwordToggle.querySelector('.eye-closed');
    
    if (type === 'text') {
        eyeOpen.style.display = 'none';
        eyeClosed.style.display = 'block';
    } else {
        eyeOpen.style.display = 'block';
        eyeClosed.style.display = 'none';
    }
});

// Form validation
// Utility for authenticated fetch
async function authFetch(url, options = {}) {
    const token = localStorage.getItem('access_token');
    if (!token) {
        window.location.href = 'index.html';
        return;
    }

    const headers = {
        ...options.headers,
        'Authorization': `Bearer ${token}`
    };

    try {
        const response = await fetch(url, { ...options, headers });
        if (response.status === 401) {
            localStorage.removeItem('access_token');
            localStorage.removeItem('user_role');
            window.location.href = 'index.html';
            return;
        }
        return response;
    } catch (error) {
        console.error('Fetch error:', error);
        throw error;
    }
}

// Get current user profile
// NOTE: real implementation is in api.js (respects DEMO_MODE).
// This stub is kept for pages that load script.js without api.js, but
// all dashboard pages load api.js first so this should never run.
async function _legacyFetchCurrentUser() {
    // Intentionally empty — use fetchCurrentUser() from api.js
}

// Update user profile — delegates to api.js implementation
// (this function is only reached if api.js is NOT loaded, which shouldn't happen)
async function _legacyUpdateProfile(data) {
    // Intentionally empty — use updateProfile() from api.js
}

// Logout
function logout() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_role');
    localStorage.removeItem('mock_role');
    window.location.href = 'index.html';
}

function showError(message) {
    if (errorText && errorMessage) {
        errorText.textContent = message;
        errorMessage.style.display = 'flex';
        
        setTimeout(() => {
            errorMessage.style.display = 'none';
        }, 5000);
    } else {
        alert(message);
    }
}

function hideError() {
    if (errorMessage) {
        errorMessage.style.display = 'none';
    }
}

// Login form submission handled in index.html inline script

// Success message
function showSuccessMessage(role) {
    const roleNames = {
        student: 'Студента',
        teacher: 'Викладача',
        admin: 'Адміністратора'
    };
    
    const successMessage = document.createElement('div');
    successMessage.className = 'success-message';
    successMessage.innerHTML = `
        <div class="success-content">
            <div class="success-icon">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/>
                    <polyline points="22 4 12 14.01 9 11.01"/>
                </svg>
            </div>
            <h3>Вхід успішний!</h3>
            <p>Ласкаво просимо, ${roleNames[role]}!</p>
            <p class="success-note">Це демо-версія. У повній версії ви будете перенаправлені на особистий кабінет.</p>
            <button class="btn btn-primary" onclick="this.parentElement.parentElement.remove()">OK</button>
        </div>
    `;
    
    document.body.appendChild(successMessage);
    
    setTimeout(() => {
        successMessage.classList.add('show');
    }, 100);
    
    // Reset form
    if (loginForm) loginForm.reset();
}

// Add success message styles
const successStyles = `
    .success-message {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 9999;
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    
    .success-message.show {
        opacity: 1;
    }
    
    .success-content {
        background: white;
        border-radius: 1rem;
        padding: 2rem;
        max-width: 400px;
        width: 90%;
        text-align: center;
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1);
    }
    
    .success-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 64px;
        height: 64px;
        background: linear-gradient(135deg, #10b981 0%, #059669 100%);
        color: white;
        border-radius: 50%;
        margin: 0 auto 1.5rem;
    }
    
    .success-content h3 {
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        color: #1f2937;
    }
    
    .success-content p {
        color: #6b7280;
        margin-bottom: 1rem;
    }
    
    .success-note {
        font-size: 0.875rem;
        color: #9ca3af;
        margin-bottom: 1.5rem;
    }
`;

const styleSheet = document.createElement('style');
styleSheet.textContent = successStyles;
document.head.appendChild(styleSheet);

// Input focus effects
if (emailInput) {
    emailInput.addEventListener('focus', () => { emailInput.parentElement.classList.add('focused'); });
    emailInput.addEventListener('blur', () => { emailInput.parentElement.classList.remove('focused'); });
}

if (passwordInput) {
    passwordInput.addEventListener('focus', () => { passwordInput.parentElement.classList.add('focused'); });
    passwordInput.addEventListener('blur', () => { passwordInput.parentElement.classList.remove('focused'); });
}

// Demo account quick fill
document.querySelectorAll('.demo-item code').forEach(codeElement => {
    codeElement.style.cursor = 'pointer';
    codeElement.addEventListener('click', () => {
        const text = codeElement.textContent;
        if (text.includes('@')) {
            emailInput.value = text;
            emailInput.focus();
        } else {
            passwordInput.value = text;
            passwordInput.focus();
        }
    });
});

// Animate elements on scroll
function animateOnScroll() {
    const elements = document.querySelectorAll('.feature-card, .stat-item, .section-header');
    
    elements.forEach(element => {
        const rect = element.getBoundingClientRect();
        const isVisible = rect.top < window.innerHeight && rect.bottom > 0;
        
        if (isVisible && !element.classList.contains('animated')) {
            element.classList.add('animated');
            element.style.animation = 'fadeIn 0.6s ease forwards';
        }
    });
}

window.addEventListener('scroll', animateOnScroll);
window.addEventListener('load', animateOnScroll);

// Add CSS for focused state
const focusStyles = `
    .input-wrapper.focused .input-icon {
        color: #2563eb;
    }
    
    .input-wrapper.focused .form-input {
        border-color: #2563eb;
    }
`;

const focusStyleSheet = document.createElement('style');
focusStyleSheet.textContent = focusStyles;
document.head.appendChild(focusStyleSheet);

// Email validation helper
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

// AI Chat Widget Implementation
const chat_widget_styles = `
.chat-container {
    position: fixed;
    bottom: 30px;
    right: 30px;
    z-index: 10000;
    font-family: 'Inter', sans-serif;
}
.chat-button {
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: linear-gradient(135deg, #2563eb 0%, #1e40af 100%);
    color: white;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    box-shadow: 0 10px 25px rgba(37, 99, 235, 0.4);
    transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.chat-button:hover {
    transform: scale(1.1);
}
.chat-window {
    position: absolute;
    bottom: 80px;
    right: 0;
    width: 350px;
    height: 500px;
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(15px);
    border: 1px solid rgba(255, 255, 255, 0.3);
    border-radius: 20px;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
    display: none;
    flex-direction: column;
    overflow: hidden;
    transform-origin: bottom right;
    transition: all 0.3s ease;
}
.chat-window.active {
    display: flex;
    animation: slideInChat 0.3s ease;
}
@keyframes slideInChat {
    from { opacity: 0; transform: translateY(20px) scale(0.9); }
    to { opacity: 1; transform: translateY(0) scale(1); }
}
.chat-header {
    padding: 20px;
    background: rgba(37, 99, 235, 0.1);
    border-bottom: 1px solid rgba(0,0,0,0.05);
    display: flex;
    align-items: center;
    gap: 12px;
}
.chat-header-info h4 { margin: 0; font-size: 16px; color: #1f2937; }
.chat-header-info p { margin: 0; font-size: 12px; color: #6b7280; }
.chat-body {
    flex: 1;
    padding: 20px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 12px;
}
.message {
    max-width: 80%;
    padding: 10px 14px;
    border-radius: 15px;
    font-size: 14px;
    line-height: 1.4;
}
.message.bot {
    background: #f3f4f6;
    color: #1f2937;
    align-self: flex-start;
    border-bottom-left-radius: 5px;
}
.message.user {
    background: #2563eb;
    color: white;
    align-self: flex-end;
    border-bottom-right-radius: 5px;
}
.chat-footer {
    padding: 15px;
    background: white;
    display: flex;
    gap: 8px;
}
.chat-input {
    flex: 1;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 8px 12px;
    outline: none;
    font-size: 14px;
}
.chat-send {
    background: #2563eb;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 8px 15px;
    cursor: pointer;
}
`;

function initGuestChatWidget() {
    // Inject styles
    const styleEl = document.createElement('style');
    styleEl.innerHTML = chat_widget_styles;
    document.head.appendChild(styleEl);

    // Create widget HTML
    const container = document.createElement('div');
    container.className = 'chat-container';
    container.innerHTML = `
        <div class="chat-window" id="chatWindow">
            <div class="chat-header">
                <div class="chat-header-icon" style="background: #2563eb; color: white; border-radius: 10px; padding: 6px;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 14l9-5-9 5-9"/></svg>
                </div>
                <div class="chat-header-info">
                    <h4>AI Асистент</h4>
                    <p>Онлайн • Готовий допомогти</p>
                </div>
            </div>
            <div class="chat-body" id="chatBody">
                <div class="message bot">Привіт! Я AI асистент IT School. Я можу відповісти на питання щодо навчання або передати запит адміністратору.</div>
            </div>
            <div class="chat-footer">
                <input type="text" class="chat-input" id="chatInput" placeholder="Ваше питання...">
                <button class="chat-send" id="chatSend">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                </button>
            </div>
        </div>
        <div class="chat-button" id="chatToggle">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        </div>
    `;
    document.body.appendChild(container);

    const toggle = document.getElementById('chatToggle');
    const window = document.getElementById('chatWindow');
    const send = document.getElementById('chatSend');
    const input = document.getElementById('chatInput');
    const body = document.getElementById('chatBody');

    toggle.addEventListener('click', () => {
        window.classList.toggle('active');
    });

    async function sendMessage() {
        const text = input.value.trim();
        if (!text) return;

        // User message
        const userMsg = document.createElement('div');
        userMsg.className = 'message user';
        userMsg.textContent = text;
        body.appendChild(userMsg);
        input.value = '';
        body.scrollTop = body.scrollHeight;

        // Fetch AI response
        const loadingMsg = document.createElement('div');
        loadingMsg.className = 'message bot';
        loadingMsg.innerHTML = '<span class="loading-dots">Думаю...</span>';
        body.appendChild(loadingMsg);

        try {
            const data = typeof askAI === 'function'
                ? await askAI(text)
                : { response: 'AI сервіс тимчасово недоступний.' };
            
            body.removeChild(loadingMsg);
            
            const botMsg = document.createElement('div');
            botMsg.className = 'message bot';
            botMsg.textContent = data.response;
            body.appendChild(botMsg);
        } catch (err) {
            loadingMsg.textContent = 'Вибачте, сталася помилка з\'єднання.';
        }
        body.scrollTop = body.scrollHeight;
    }

    send.addEventListener('click', sendMessage);
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage();
    });
}

function isIndexPage() {
    const path = window.location.pathname.replace(/\\/g, '/').toLowerCase();
    return path.endsWith('/index.html') || path === '/' || path === '';
}

// Initialize
updateHeader();
updateActiveNav();
animateOnScroll();

// Guest AI widget: only on landing page and only before login.
if (!localStorage.getItem('access_token') && isIndexPage()) {
    initGuestChatWidget();
}
