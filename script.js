/**
 * Theme Engine - Динамический регулятор яркости (Dark -> Light)
 */
const ThemeEngine = {
    // Цветовые точки (Dark -> Light)
    themes: {
        dark: {
            bg: [10, 10, 15],
            text: [255, 255, 255],
            textDim: [160, 160, 176],
            surface: [20, 20, 30, 0.4],
            border: [255, 255, 255, 0.08]
        },
        light: {
            bg: [248, 250, 252],
            text: [15, 17, 26],
            textDim: [100, 116, 139],
            surface: [255, 255, 255, 0.8],
            border: [0, 0, 0, 0.05]
        }
    },

    init: function() {
        const savedValue = localStorage.getItem('enikey_brightness') || 0;
        this.apply(savedValue);
        
        // Поиск слайдера на странице (может быть несколько на разных страницах)
        const sliders = document.querySelectorAll('.brightness-slider');
        sliders.forEach(slider => {
            slider.value = savedValue;
            slider.addEventListener('input', (e) => {
                this.apply(e.target.value);
                // Синхронизация всех слайдеров на странице
                sliders.forEach(s => s.value = e.target.value);
            });
        });
    },

    apply: function(value) {
        const factor = value / 100;
        const root = document.documentElement;
        
        const lerp = (a, b, f) => Math.round(a + (b - a) * f);
        const lerpAlpha = (a, b, f) => (parseFloat(a) + (parseFloat(b) - parseFloat(a)) * f).toFixed(2);

        // Расчет цветов
        const bg = this.themes.dark.bg.map((val, i) => lerp(val, this.themes.light.bg[i], factor));
        const text = this.themes.dark.text.map((val, i) => lerp(val, this.themes.light.text[i], factor));
        const textDim = this.themes.dark.textDim.map((val, i) => lerp(val, this.themes.light.textDim[i], factor));
        
        const surfaceRgb = this.themes.dark.surface.slice(0, 3).map((val, i) => lerp(val, this.themes.light.surface[i], factor));
        const surfaceA = lerpAlpha(this.themes.dark.surface[3], this.themes.light.surface[3], factor);
        
        const borderRgb = this.themes.dark.border.slice(0, 3).map((val, i) => lerp(val, this.themes.light.border[i], factor));
        const borderA = lerpAlpha(this.themes.dark.border[3], this.themes.light.border[3], factor);

        // Применение переменных
        root.style.setProperty('--bg-base', `rgb(${bg.join(',')})`);
        root.style.setProperty('--text-primary', `rgb(${text.join(',')})`);
        root.style.setProperty('--text-secondary', `rgb(${textDim.join(',')})`);
        root.style.setProperty('--bg-surface', `rgba(${surfaceRgb.join(',')}, ${surfaceA})`);
        root.style.setProperty('--glass-border', `rgba(${borderRgb.join(',')}, ${borderA})`);
        
        localStorage.setItem('enikey_brightness', value);
    }
};

document.addEventListener('DOMContentLoaded', () => {
    ThemeEngine.init();
    // Reveal elements on scroll
    const reveals = document.querySelectorAll('.reveal');

    function reveal() {
        const windowHeight = window.innerHeight;
        const elementVisible = 150;

        reveals.forEach((reveal) => {
            const elementTop = reveal.getBoundingClientRect().top;
            if (elementTop < windowHeight - elementVisible) {
                reveal.classList.add('active');
            }
        });
    }

    // Initial check
    reveal();

    // Scroll listener for reveals and navbar
    const navbar = document.querySelector('.navbar');
    window.addEventListener('scroll', () => {
        reveal();
        
        // Navbar glass effect enhancement on scroll
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });

    // Advanced 3D Tilt & Glow effect for interactive cards
    function initTilt() {
        const interactiveCards = document.querySelectorAll('.interactive-card');
        
        interactiveCards.forEach(card => {
            // Avoid double binding
            if (card.dataset.tiltInitialized) return;
            card.dataset.tiltInitialized = "true";

            const glow = card.querySelector('.card-glow');
            
            card.addEventListener('mousemove', (e) => {
                const rect = card.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                
                card.style.transition = 'transform 0.1s ease-out, border-color 0.3s';
                
                if(glow) {
                    glow.style.left = `${x}px`;
                    glow.style.top = `${y}px`;
                    glow.style.opacity = '1';
                }
                
                const centerX = rect.width / 2;
                const centerY = rect.height / 2;
                const tiltX = ((x - centerX) / centerX) * 5;
                const tiltY = ((centerY - y) / centerY) * 5;
                
                card.style.transform = `perspective(1000px) rotateX(${tiltY}deg) rotateY(${tiltX}deg) scale3d(1.02, 1.02, 1.02)`;
            });
            
            card.addEventListener('mouseleave', () => {
                card.style.transition = 'transform 0.5s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.4s';
                if(glow) glow.style.opacity = '0';
                card.style.transform = `perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)`;
            });
        });
    }

    initTilt();

    // Mouse Tracking for Particles
    let mouseX = window.innerWidth / 2;
    let mouseY = window.innerHeight / 2;

    document.addEventListener('mousemove', (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;
    });

    // Particles Background
    const canvas = document.getElementById('particles-bg');
    if (canvas) {
        const ctx = canvas.getContext('2d');
        let width = canvas.width = window.innerWidth;
        let height = canvas.height = window.innerHeight;
        
        const particles = [];
        const particleCount = Math.floor(width * height / 12000);
        
        class Particle {
            constructor() {
                this.x = Math.random() * width;
                this.y = Math.random() * height;
                this.vx = (Math.random() - 0.5) * 0.5;
                this.vy = (Math.random() - 0.5) * 0.5;
                this.radius = Math.random() * 1.5 + 0.5;
            }
            update() {
                this.x += this.vx;
                this.y += this.vy;
                
                if (this.x < 0 || this.x > width) this.vx *= -1;
                if (this.y < 0 || this.y > height) this.vy *= -1;
            }
            draw() {
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
                const isLight = (window.ThemeEngine?.currentBrightness || 0) > 50;
                ctx.fillStyle = isLight ? 'rgba(138, 43, 226, 0.2)' : 'rgba(138, 43, 226, 0.4)';
                ctx.fill();
            }
        }
        
        for (let i = 0; i < particleCount; i++) {
            particles.push(new Particle());
        }
        
        function drawParticles() {
            ctx.clearRect(0, 0, width, height);
            const isLight = (window.ThemeEngine?.currentBrightness || 0) > 50;
            
            for (let i = 0; i < particles.length; i++) {
                particles[i].update();
                particles[i].draw();
                
                for (let j = i + 1; j < particles.length; j++) {
                    const dx = particles[i].x - particles[j].x;
                    const dy = particles[i].y - particles[j].y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    
                    if (dist < 100) {
                        ctx.beginPath();
                        ctx.moveTo(particles[i].x, particles[i].y);
                        ctx.lineTo(particles[j].x, particles[j].y);
                        
                        const mdx = particles[i].x - mouseX;
                        const mdy = particles[i].y - mouseY;
                        const mdist = Math.sqrt(mdx * mdx + mdy * mdy);
                        
                        let opacity = 1 - (dist / 100);
                        if (mdist < 150) {
                            opacity = opacity * 2;
                            ctx.strokeStyle = `rgba(138, 43, 226, ${opacity})`;
                            ctx.lineWidth = 1;
                        } else {
                            ctx.strokeStyle = isLight ? `rgba(0, 0, 0, ${opacity * 0.05})` : `rgba(255, 255, 255, ${opacity * 0.1})`;
                            ctx.lineWidth = 0.5;
                        }
                        ctx.stroke();
                    }
                }
            }
            requestAnimationFrame(drawParticles);
        }
        
        function resize() {
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
            particles.length = 0;
            const newParticleCount = Math.floor(width * height / 12000);
            for (let i = 0; i < newParticleCount; i++) {
                particles.push(new Particle());
            }
        }

        drawParticles();
        window.addEventListener('resize', resize);
    }

    // Typing Simulator for Visual Code Editor
    const codeBlock = document.querySelector('.code-editor code');
    if (codeBlock) {
        const originalText = codeBlock.textContent;
        codeBlock.textContent = '';
        let charIndex = 0;
        
        setTimeout(() => {
            function typeChar() {
                if (charIndex < originalText.length) {
                    codeBlock.textContent += originalText.charAt(charIndex);
                    charIndex++;
                    setTimeout(typeChar, Math.random() * 15 + 5);
                }
            }
            typeChar();
        }, 800);
    }

    // Mobile menu toggle animation
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const navLinks = document.querySelector('.nav-links');
    
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', () => {
            const spans = mobileMenuBtn.querySelectorAll('span');
            mobileMenuBtn.classList.toggle('active');
            
            if (mobileMenuBtn.classList.contains('active')) {
                spans[0].style.transform = 'rotate(45deg) translate(5px, 5px)';
                spans[1].style.opacity = '0';
                spans[2].style.transform = 'rotate(-45deg) translate(5px, -5px)';
                navLinks.classList.add('mobile-active');
            } else {
                spans[0].style.transform = 'none';
                spans[1].style.opacity = '1';
                spans[2].style.transform = 'none';
                navLinks.classList.remove('mobile-active');
            }
        });
    }

    // Close mobile menu when a link is clicked
    if (navLinks) {
        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                if (window.innerWidth <= 900 && mobileMenuBtn && mobileMenuBtn.classList.contains('active')) {
                    mobileMenuBtn.click();
                }
            });
        });
    }

    // UI Elements
    const langBtns = document.querySelectorAll('.lang-btn');
    const elementsToTranslate = document.querySelectorAll('[data-i18n]');
    const newsContainer = document.getElementById('news-container');
    const articlesContainer = document.getElementById('articles-container');
    const articleHeader = document.getElementById('article-header');
    const articleText = document.getElementById('article-text');
    const sidebarNews = document.getElementById('sidebar-news');
    const commentsList = document.getElementById('comments-list');
    const submitBtn = document.getElementById('submit-comment');
    const commentInput = document.getElementById('comment-input');

    // Pulse Data handling via PulseAPI
    async function getPulseData() {
        if (window.PulseAPI) {
            return await window.PulseAPI.getPublished();
        }
        return { news: [], articles: [] };
    }

    let localComments = [
        { id: 101, author: "TechMaster", text: "Это действительно впечатляет! Жду не дождусь нейроморфных обновлений.", date: "1 час назад", isAI: false },
        { id: 102, author: "Enikey Software Support", text: "Согласны! Мы уже тестируем первые прототипы с адаптивными компонентами.", date: "50 мин назад", isAI: false }
    ];

    function renderComments(list, container) {
        if (!container) return;
        const lang = localStorage.getItem('lang') || 'ru';
        container.innerHTML = list.map(c => `
            <div class="comment-item ${c.author === 'Enikey Software Support' ? 'ai-response' : ''} reveal active">
                <div class="comment-avatar"></div>
                <div class="comment-content">
                    <div class="comment-header">
                        <span class="comment-author">${c.author}</span>
                        <span class="comment-date">${c.date}</span>
                    </div>
                    <div class="comment-text">${c.text}</div>
                    <div class="comment-actions">
                        <button>${lang === 'ru' ? 'Ответить' : lang === 'en' ? 'Reply' : '回复'}</button>
                        <button>${lang === 'ru' ? 'Лайк' : lang === 'en' ? 'Like' : '赞'}</button>
                    </div>
                </div>
            </div>
        `).join('');
    }

    function addComment(text) {
        const newId = Date.now();
        localComments.push({ id: newId, author: "Гость", text: text, date: "Только что", isAI: false });
        renderComments(localComments, commentsList);
        
        setTimeout(() => {
            localComments.push({
                id: newId + 1,
                author: "Enikey Software Support",
                text: "Интересная мысль! Мы проверили ваш комментарий. Давайте обсудим это подробнее.",
                date: "Только что",
                isAI: false
            });
            renderComments(localComments, commentsList);
        }, 2000);
    }

    if (submitBtn) {
        submitBtn.addEventListener('click', () => {
            if (commentInput.value.trim()) {
                addComment(commentInput.value);
                commentInput.value = '';
            }
        });
    }

    async function renderPulse() {
        const lang = localStorage.getItem('lang') || 'ru';
        const data = await getPulseData();
        
        if (newsContainer) {
            newsContainer.innerHTML = data.news.map(item => `
                <div class="glass-card post-card mini-card reveal active">
                    <div class="post-meta"><span>${item.publishedAt ? new Date(item.publishedAt).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'}) : 'Недавно'}</span> • <span data-i18n="ai_moderated">${translations[lang].ai_moderated}</span></div>
                    <h3>${item.title[lang]}</h3>
                    <p>${item.excerpt[lang]}</p>
                </div>
            `).join('');
        }

        if (articlesContainer) {
            articlesContainer.innerHTML = data.articles.map(item => `
                <div class="glass-card article-card interactive-card reveal active">
                    <div class="card-glow"></div>
                    <div class="article-image-wrapper">
                        <img src="${item.image}" alt="Featured Article" class="article-image">
                    </div>
                    <div class="article-content">
                        <div class="post-meta"><span>${item.publishedAt ? new Date(item.publishedAt).toLocaleDateString() : 'Недавно'}</span> • <span>5 мин ${lang === 'ru' ? 'чтения' : lang === 'en' ? 'read' : '阅读时间'}</span></div>
                        <h3>${item.title[lang]}</h3>
                        <p>${item.desc ? item.desc[lang] : item.excerpt[lang]}</p>
                        <a href="article.html?id=${item.id}" class="btn btn-outline btn-small" data-i18n="read_more">${translations[lang].read_more}</a>
                    </div>
                </div>
            `).join('');
        }

        const urlParams = new URLSearchParams(window.location.search);
        const articleId = urlParams.get('id');
        if (articleId) {
            const art = data.articles.find(a => a.id == articleId) || (data.news.find(n => n.id == articleId));
            if (art) {
                if (articleHeader) articleHeader.innerHTML = `<div class="article-hero"><img src="${art.image || 'agency_tech_abstract.png'}" alt="Hero"></div>`;
                if (articleText) articleText.innerHTML = art.content ? art.content[lang] : `<h1>${art.title[lang]}</h1><p>${art.excerpt[lang]}</p>`;
                if (sidebarNews) {
                    sidebarNews.innerHTML = data.news.map(n => `
                        <div class="glass-card post-card mini-card reveal active" onclick="window.location.href='article.html?id=${n.id}'">
                            <h3>${n.title[lang]}</h3>
                        </div>
                    `).join('');
                }
                renderComments(localComments, commentsList);
            }
        }

        initTilt();
    }

    async function setLanguage(lang) {
        if (!translations[lang]) return;
        localStorage.setItem('lang', lang);
        document.documentElement.lang = lang;

        langBtns.forEach(btn => {
            if (btn.dataset.lang === lang) btn.classList.add('active');
            else btn.classList.remove('active');
        });

        elementsToTranslate.forEach(el => {
            const key = el.dataset.i18n;
            if (translations[lang] && translations[lang][key]) {
                if (el.dataset.i18nHtml === "true") el.innerHTML = translations[lang][key];
                else el.textContent = translations[lang][key];
            }
        });

        await renderPulse();
    }

    langBtns.forEach(btn => {
        btn.addEventListener('click', () => setLanguage(btn.dataset.lang));
    });

    const savedLang = localStorage.getItem('lang') || 'ru';
    setLanguage(savedLang);
});
