(() => {
  const titles = {
    home: { ru: 'Enikey — разработка программных решений', en: 'Enikey — Software Development' },
    news: { ru: 'Новости и статьи — Enikey', en: 'News and articles — Enikey' },
    article: { ru: 'Публикация — Enikey', en: 'Article — Enikey' }
  };

  function setLanguage(language) {
    document.documentElement.lang = language;
    document.querySelectorAll('[data-ru][data-en]').forEach((element) => {
      element.textContent = element.dataset[language];
    });
    document.querySelectorAll('[data-language]').forEach((button) => {
      const active = button.dataset.language === language;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    const page = document.body.dataset.page || 'home';
    if (titles[page]) document.title = titles[page][language];
    try { localStorage.setItem('enikey_site_language', language); } catch (error) {}
    window.dispatchEvent(new Event('enikey-language-change'));
  }

  document.querySelectorAll('[data-language]').forEach((button) => {
    button.addEventListener('click', () => setLanguage(button.dataset.language));
  });

  let initialLanguage = 'ru';
  try {
    if (localStorage.getItem('enikey_site_language') === 'en') initialLanguage = 'en';
  } catch (error) {}
  setLanguage(initialLanguage);

  const year = document.getElementById('current-year');
  if (year) year.textContent = new Date().getFullYear();
})();
