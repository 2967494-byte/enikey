document.addEventListener('DOMContentLoaded', () => {
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
    const interactiveCards = document.querySelectorAll('.interactive-card');
    
    interactiveCards.forEach(card => {
        const glow = card.querySelector('.card-glow');
        
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            // Temporary fast transition for instant follow
            card.style.transition = 'transform 0.1s ease-out, border-color 0.3s';
            
            // Glow positioning
            if(glow) {
                glow.style.left = `${x}px`;
                glow.style.top = `${y}px`;
                glow.style.opacity = '1';
            }
            
            // 3D Tilt calculations
            const centerX = rect.width / 2;
            const centerY = rect.height / 2;
            const tiltX = ((x - centerX) / centerX) * 5; // max rotation 5deg
            const tiltY = ((centerY - y) / centerY) * 5; // max rotation 5deg
            
            card.style.transform = `perspective(1000px) rotateX(${tiltY}deg) rotateY(${tiltX}deg) scale3d(1.02, 1.02, 1.02)`;
        });
        
        card.addEventListener('mouseleave', () => {
            card.style.transition = 'transform 0.5s cubic-bezier(0.16, 1, 0.3, 1), border-color 0.4s'; // smooth reset
            if(glow) glow.style.opacity = '0';
            card.style.transform = `perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)`;
        });
    });

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
                ctx.fillStyle = 'rgba(138,43,226, 0.4)';
                ctx.fill();
            }
        }
        
        for (let i = 0; i < particleCount; i++) {
            particles.push(new Particle());
        }
        
        function drawParticles() {
            ctx.clearRect(0, 0, width, height);
            
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
                            ctx.strokeStyle = `rgba(255, 255, 255, ${opacity * 0.1})`;
                            ctx.lineWidth = 0.5;
                        }
                        ctx.stroke();
                    }
                }
            }
            requestAnimationFrame(drawParticles);
        }
        
        drawParticles();
        
        window.addEventListener('resize', () => {
            width = canvas.width = window.innerWidth;
            height = canvas.height = window.innerHeight;
            particles.length = 0;
            const newParticleCount = Math.floor(width * height / 12000);
            for (let i = 0; i < newParticleCount; i++) {
                particles.push(new Particle());
            }
        });
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
    
    mobileMenuBtn.addEventListener('click', () => {
        // Toggle animation for burger icon
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

    // Close mobile menu when a link is clicked
    navLinks.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => {
            if (window.innerWidth <= 900 && mobileMenuBtn.classList.contains('active')) {
                mobileMenuBtn.click();
            }
        });
    });

    // Language Switcher Logic
    const langBtns = document.querySelectorAll('.lang-btn');
    const elementsToTranslate = document.querySelectorAll('[data-i18n]');

    function setLanguage(lang) {
        if (!translations[lang]) return;
        localStorage.setItem('lang', lang);
        document.documentElement.lang = lang;

        // Update active class
        langBtns.forEach(btn => {
            if (btn.dataset.lang === lang) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        // Translate elements
        elementsToTranslate.forEach(el => {
            const key = el.dataset.i18n;
            if (translations[lang][key]) {
                if (el.dataset.i18nHtml === "true") {
                    el.innerHTML = translations[lang][key];
                } else {
                    el.textContent = translations[lang][key];
                }
            }
        });
    }

    langBtns.forEach(btn => {
        btn.addEventListener('click', () => setLanguage(btn.dataset.lang));
    });

    // Initialize Language
    const savedLang = localStorage.getItem('lang') || 'ru';
    setLanguage(savedLang);
});
