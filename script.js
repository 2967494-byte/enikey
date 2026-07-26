/**
 * Enikey Software - Next-Gen IDE Experience Engine
 */

// Web Audio API Soft Click Generator (No external audio files required)
const AudioFX = {
    ctx: null,
    enabled: true,
    init: function() {
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext) {
                this.ctx = new AudioContext();
            }
        } catch (e) {
            console.warn('Web Audio API not supported', e);
        }
    },
    playClick: function(freq = 800, duration = 0.03) {
        if (!this.enabled || !this.ctx) return;
        if (this.ctx.state === 'suspended') {
            this.ctx.resume();
        }
        try {
            const osc = this.ctx.createOscillator();
            const gain = this.ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, this.ctx.currentTime);
            osc.frequency.exponentialRampToValueAtTime(freq / 2, this.ctx.currentTime + duration);
            gain.gain.setValueAtTime(0.08, this.ctx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, this.ctx.currentTime + duration);
            osc.connect(gain);
            gain.connect(this.ctx.destination);
            osc.start();
            osc.stop(this.ctx.currentTime + duration);
        } catch (e) {
            // Ignore audio errors
        }
    }
};

// Theme & Palette Engine
const ThemeEngine = {
    init: function() {
        const savedTheme = localStorage.getItem('enikey_theme') || 'dark';
        const savedPalette = localStorage.getItem('enikey_palette') || 'violet';
        
        this.setTheme(savedTheme);
        this.setPalette(savedPalette);

        // Bind legacy sliders if present
        const sliders = document.querySelectorAll('.brightness-slider');
        sliders.forEach(slider => {
            slider.value = savedTheme === 'light' ? 100 : savedTheme === 'cyber' ? 50 : 0;
            slider.addEventListener('input', (e) => {
                const val = parseInt(e.target.value);
                const theme = val > 70 ? 'light' : val > 30 ? 'cyber' : 'dark';
                this.setTheme(theme);
            });
        });
    },
    setTheme: function(theme) {
        document.body.setAttribute('data-theme', theme);
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('enikey_theme', theme);
        
        document.querySelectorAll('.theme-option-btn').forEach(btn => {
            if (btn.dataset.theme === theme) btn.classList.add('active');
            else btn.classList.remove('active');
        });
    },
    setPalette: function(palette) {
        document.body.setAttribute('data-palette', palette);
        document.documentElement.setAttribute('data-palette', palette);
        localStorage.setItem('enikey_palette', palette);
        
        document.querySelectorAll('.palette-swatch').forEach(btn => {
            if (btn.dataset.palette === palette) btn.classList.add('active');
            else btn.classList.remove('active');
        });
    }
};

// IDE Control Panel & Interaction Engine
const IDESettings = {
    particleDensity: 90,
    particleSpeed: 4,

    init: function() {
        const panel = document.getElementById('ide-settings-panel');
        const toggleBtn = document.getElementById('ide-toggle-btn');
        const gridOverlay = document.getElementById('dev-grid-overlay');
        const cursorGlow = document.getElementById('cursor-glow-follower');
        
        // Toggle Sidebar & Outside Click Close
        if (toggleBtn && panel) {
            toggleBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                panel.classList.toggle('open');
                AudioFX.playClick(600);
            });

            document.addEventListener('click', (e) => {
                if (panel.classList.contains('open') && !panel.contains(e.target)) {
                    panel.classList.remove('open');
                    AudioFX.playClick(500);
                }
            });
        }

        // Theme Options
        document.querySelectorAll('.theme-option-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const theme = e.currentTarget.dataset.theme;
                ThemeEngine.setTheme(theme);
                AudioFX.playClick(700);
            });
        });

        // Palette Options
        document.querySelectorAll('.palette-swatch').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const palette = e.currentTarget.dataset.palette;
                ThemeEngine.setPalette(palette);
                AudioFX.playClick(900);
            });
        });

        // Grid Overlay Toggle
        const gridCheckbox = document.getElementById('toggle-grid');
        if (gridCheckbox && gridOverlay) {
            gridCheckbox.addEventListener('change', (e) => {
                if (e.target.checked) gridOverlay.classList.add('active');
                else gridOverlay.classList.remove('active');
                AudioFX.playClick(500);
            });
        }

        // Cursor Glow Toggle
        const cursorCheckbox = document.getElementById('toggle-cursor');
        if (cursorCheckbox && cursorGlow) {
            cursorCheckbox.addEventListener('change', (e) => {
                if (e.target.checked) cursorGlow.classList.add('active');
                else cursorGlow.classList.remove('active');
                AudioFX.playClick(500);
            });
            if (cursorCheckbox.checked) cursorGlow.classList.add('active');
        }

        // Audio Toggle
        const audioCheckbox = document.getElementById('toggle-audio');
        if (audioCheckbox) {
            audioCheckbox.addEventListener('change', (e) => {
                AudioFX.enabled = e.target.checked;
                if (e.target.checked) AudioFX.playClick(1000);
            });
        }

        // Slider Controls
        const densitySlider = document.getElementById('density-slider');
        const speedSlider = document.getElementById('speed-slider');

        if (densitySlider) {
            densitySlider.addEventListener('input', (e) => {
                this.particleDensity = parseInt(e.target.value);
            });
        }

        if (speedSlider) {
            speedSlider.addEventListener('input', (e) => {
                this.particleSpeed = parseInt(e.target.value);
            });
        }
    }
};

// Hero Dev Workspace Tabs Engine
const HeroWorkspace = {
    snippets: {
        architecture: `<span class="kwd">import</span> { <span class="type">Architect</span>, <span class="type">HighLoad</span> } <span class="kwd">from</span> <span class="str">'@enikey/core'</span>;

<span class="kwd">export class</span> <span class="type">EnikeySystem</span> <span class="kwd">implements</span> <span class="type">Architect</span> {
    <span class="kwd">readonly</span> UI = <span class="str">"Bespoke Glassmorphism 2.0"</span>;
    <span class="kwd">readonly</span> Architecture = <span class="str">"Microservices & Async Workers"</span>;

    <span class="kwd">async</span> <span class="func">deployFuture</span>() {
        <span class="kwd">return await</span> <span class="type">HighLoad</span>.<span class="func">compile</span>({ speed: <span class="str">"60 FPS"</span>, latency: <span class="str">"&lt;20ms"</span> });
    }
}`,
        performance: `<span class="kwd">use</span> enikey_engine::<span class="type">Reactor</span>;

<span class="kwd">pub fn</span> <span class="func">main</span>() -> <span class="type">Result</span>&lt;(), <span class="type">EngineError</span>&gt; {
    <span class="kwd">let mut</span> app = <span class="type">Reactor</span>::<span class="func">new</span>();
    app.<span class="func">enable_zero_copy_cache</span>();
    app.<span class="func">dispatch_threads</span>(<span class="str">32</span>);
    
    println!(<span class="str">"System state: 200 OK [Latency: 14ms]"</span>);
    <span class="type">Ok</span>(())
}`,
        crzrt: `<span class="kwd">import</span> { <span class="type">CRZRTCore</span> } <span class="kwd">from</span> <span class="str">'https://zakupki.tatar/'</span>;

<span class="kwd">const</span> crzrt = <span class="kwd">new</span> <span class="type">CRZRTCore</span>({
    domain: <span class="str">"https://zakupki.tatar/"</span>,
    modules: [<span class="str">"Тендерное сопровождение"</span>, <span class="str">"Обучение 44-ФЗ"</span>, <span class="str">"Консалтинг"</span>, <span class="str">"ЭТП"</span>],
    performance: <span class="str">"Ultra-Fast"</span>
});

crzrt.<span class="func">initializeEcosystem</span>();`
    },
    init: function() {
        const codeElement = document.getElementById('workspace-code');
        const tabBtns = document.querySelectorAll('.ws-tab');
        const runBtn = document.getElementById('run-code-btn');
        const terminalText = document.querySelector('.terminal-status .status-text');

        if (!codeElement) return;

        tabBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tab = e.currentTarget.dataset.tab;
                tabBtns.forEach(b => b.classList.remove('active'));
                e.currentTarget.classList.add('active');

                if (this.snippets[tab]) {
                    codeElement.innerHTML = `<code class="language-typescript">${this.snippets[tab]}</code>`;
                }
                AudioFX.playClick(750);
            });
        });

        if (runBtn) {
            runBtn.addEventListener('click', () => {
                AudioFX.playClick(1100);
                if (terminalText) {
                    terminalText.textContent = "[RE-COMPILING...] Executing optimize_pipeline()";
                    setTimeout(() => {
                        terminalText.textContent = `[BUILD OK] Compiled in ${Math.floor(Math.random() * 15 + 15)}ms • All 48 tests passed`;
                    }, 400);
                }
            });
        }
    }
};

function getAccentRGB() {
    const raw = getComputedStyle(document.body).getPropertyValue('--accent-rgb').trim();
    if (raw && raw.includes(',')) return raw;
    const palette = document.body.getAttribute('data-palette') || 'violet';
    const map = {
        violet: '138, 43, 226',
        emerald: '16, 185, 129',
        cyan: '6, 182, 212',
        amber: '245, 158, 11'
    };
    return map[palette] || '138, 43, 226';
}

// Canvas Background Particle Engine (Interactive connecting lines)
function initCanvasParticles() {
    const canvas = document.getElementById('particles-bg');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    let width = canvas.width = window.innerWidth;
    let height = canvas.height = window.innerHeight;

    const particles = [];
    
    function createParticles() {
        particles.length = 0;
        const count = Math.floor((width * height) / (20000 - IDESettings.particleDensity * 80));
        for (let i = 0; i < count; i++) {
            particles.push({
                x: Math.random() * width,
                y: Math.random() * height,
                vx: (Math.random() - 0.5) * (IDESettings.particleSpeed * 0.25),
                vy: (Math.random() - 0.5) * (IDESettings.particleSpeed * 0.25),
                radius: Math.random() * 1.5 + 0.8
            });
        }
    }

    createParticles();

    let mouseX = width / 2;
    let mouseY = height / 2;

    document.addEventListener('mousemove', (e) => {
        mouseX = e.clientX;
        mouseY = e.clientY;
    });

    function draw() {
        ctx.clearRect(0, 0, width, height);
        const rgb = getAccentRGB();
        const isLight = document.body.getAttribute('data-theme') === 'light';

        for (let i = 0; i < particles.length; i++) {
            const p = particles[i];

            // Magnetic attraction to cursor
            const mdx = mouseX - p.x;
            const mdy = mouseY - p.y;
            const mdist = Math.sqrt(mdx * mdx + mdy * mdy);

            if (mdist < 180 && mdist > 0) {
                p.x += (mdx / mdist) * 0.7;
                p.y += (mdy / mdist) * 0.7;
            }

            p.x += p.vx * (IDESettings.particleSpeed / 4);
            p.y += p.vy * (IDESettings.particleSpeed / 4);

            if (p.x < 0 || p.x > width) p.vx *= -1;
            if (p.y < 0 || p.y > height) p.vy *= -1;

            ctx.beginPath();
            ctx.arc(p.x, p.y, p.radius * 1.3, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${rgb}, ${isLight ? 0.85 : 0.9})`;
            ctx.fill();

            // Connect directly to mouse cursor
            if (mdist < 180) {
                const mouseAlpha = (1 - mdist / 180) * 0.75;
                ctx.beginPath();
                ctx.moveTo(p.x, p.y);
                ctx.lineTo(mouseX, mouseY);
                ctx.strokeStyle = `rgba(${rgb}, ${mouseAlpha})`;
                ctx.lineWidth = 1.2;
                ctx.stroke();
            }

            for (let j = i + 1; j < particles.length; j++) {
                const p2 = particles[j];
                const dx = p.x - p2.x;
                const dy = p.y - p2.y;
                const dist = Math.sqrt(dx * dx + dy * dy);

                if (dist < 130) {
                    ctx.beginPath();
                    ctx.moveTo(p.x, p.y);
                    ctx.lineTo(p2.x, p2.y);

                    let alpha = 1 - (dist / 130);
                    if (mdist < 160) {
                        alpha = Math.min(1, alpha * 2.5);
                        ctx.strokeStyle = `rgba(${rgb}, ${alpha * 0.95})`;
                        ctx.lineWidth = 1.3;
                    } else {
                        ctx.strokeStyle = `rgba(${rgb}, ${alpha * (isLight ? 0.45 : 0.35)})`;
                        ctx.lineWidth = 0.8;
                    }
                    ctx.stroke();
                }
            }
        }
        requestAnimationFrame(draw);
    }

    draw();

    window.addEventListener('resize', () => {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
        createParticles();
    });
}

// 3D Card Tilt & Mouse Tracking Glow Effect
function initTiltAndGlow() {
    const cards = document.querySelectorAll('.interactive-card');
    
    cards.forEach(card => {
        if (card.dataset.tiltInitialized) return;
        card.dataset.tiltInitialized = "true";

        const glow = card.querySelector('.card-glow');

        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            if (glow) {
                glow.style.left = `${x}px`;
                glow.style.top = `${y}px`;
                glow.style.opacity = '1';
            }

            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            const tiltX = ((x - centerX) / centerX) * 4;
            const tiltY = ((centerY - y) / centerY) * 4;

            card.style.transform = `perspective(1000px) rotateX(${tiltY}deg) rotateY(${tiltX}deg) scale3d(1.01, 1.01, 1.01)`;
        });

        card.addEventListener('mouseleave', () => {
            if (glow) glow.style.opacity = '0';
            card.style.transform = `perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)`;
        });
    });
}

// Scroll Observer & IDE Status Bar Tracking
function initScrollEngine() {
    const statusLine = document.getElementById('status-line');
    const statusCol = document.getElementById('status-col');
    const statusSection = document.getElementById('status-section');
    const statusScrollPct = document.getElementById('status-scroll-pct');
    const cursorGlow = document.getElementById('cursor-glow-follower');

    const sections = document.querySelectorAll('section[id]');
    const reveals = document.querySelectorAll('.reveal');

    // Reveal animations on scroll
    function handleScroll() {
        const windowHeight = window.innerHeight;
        const totalHeight = document.documentElement.scrollHeight - windowHeight;
        const scrollY = window.scrollY;
        
        // Scroll % Calculation
        const scrollPct = Math.round((scrollY / Math.max(1, totalHeight)) * 100);
        if (statusScrollPct) statusScrollPct.textContent = `${scrollPct}%`;

        // Pseudo Line / Col Counter
        if (statusLine) statusLine.textContent = Math.floor(scrollY / 15) + 1;
        if (statusCol) statusCol.textContent = (scrollY % 60) + 1;

        // Active Section Tracking
        sections.forEach(sec => {
            const top = sec.offsetTop - 150;
            const height = sec.offsetHeight;
            if (scrollY >= top && scrollY < top + height) {
                if (statusSection) statusSection.textContent = `${sec.id.toUpperCase()}.TS`;
            }
        });

        // Reveal Activation
        reveals.forEach(el => {
            const elementTop = el.getBoundingClientRect().top;
            if (elementTop < windowHeight - 100) {
                el.classList.add('active');
            }
        });
    }

    window.addEventListener('scroll', handleScroll);
    handleScroll();

    // Cursor Follower Movement
    document.addEventListener('mousemove', (e) => {
        if (cursorGlow && cursorGlow.classList.contains('active')) {
            cursorGlow.style.left = `${e.clientX}px`;
            cursorGlow.style.top = `${e.clientY}px`;
        }
    });
}

// Global Initialization
document.addEventListener('DOMContentLoaded', () => {
    AudioFX.init();
    ThemeEngine.init();
    IDESettings.init();
    HeroWorkspace.init();
    initCanvasParticles();
    initTiltAndGlow();
    initScrollEngine();

    // Mobile Menu Toggle
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const navLinks = document.querySelector('.nav-links');

    if (mobileMenuBtn && navLinks) {
        mobileMenuBtn.addEventListener('click', () => {
            mobileMenuBtn.classList.toggle('active');
            navLinks.classList.toggle('mobile-active');
            AudioFX.playClick(650);
        });
    }

    // Attach click sound to buttons
    document.querySelectorAll('.btn, .nav-links a, .social-icon').forEach(el => {
        el.addEventListener('click', () => AudioFX.playClick(850));
    });
});
