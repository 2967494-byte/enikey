(() => {
  const apiBase = window.API_CONFIG?.BASE_URL || '/api';

  function language() {
    return document.documentElement.lang === 'en' ? 'en' : 'ru';
  }

  function localized(value) {
    if (typeof value === 'string') return value;
    return value?.[language()] || value?.ru || '';
  }

  function formatDate(value) {
    const date = new Date(`${value.replace(' ', 'T')}Z`);
    if (Number.isNaN(date.getTime())) return '';
    return new Intl.DateTimeFormat(language() === 'en' ? 'en-GB' : 'ru-RU', {
      day: 'numeric', month: 'long', year: 'numeric', timeZone: 'Europe/Moscow'
    }).format(date);
  }

  function linkFor(post) {
    return `news-detail.html?id=${encodeURIComponent(post.id)}`;
  }

  function makeTextItem(post) {
    const link = document.createElement('a');
    link.className = 'news-text-item';
    link.href = linkFor(post);
    const title = document.createElement('h3');
    title.className = 'news-item-title';
    title.textContent = localized(post.title);
    link.append(title);
    const summaryText = localized(post.summary);
    if (summaryText) {
      const summary = document.createElement('p');
      summary.className = 'news-item-summary';
      summary.textContent = summaryText;
      link.append(summary);
    }
    const date = document.createElement('time');
    date.className = 'news-item-date';
    date.dateTime = post.createdAt;
    date.textContent = formatDate(post.createdAt);
    link.append(date);
    return link;
  }

  function makeImageItem(post, className = 'news-image-item') {
    const link = document.createElement('a');
    link.className = className;
    link.href = linkFor(post);
    const frame = document.createElement('div');
    frame.className = 'news-image-frame';
    const image = document.createElement('img');
    image.src = post.imageUrl;
    image.alt = localized(post.title);
    image.loading = 'lazy';
    frame.append(image);
    const copy = document.createElement('div');
    copy.className = 'news-image-copy';
    const title = document.createElement('h3');
    title.className = 'news-item-title';
    title.textContent = localized(post.title);
    copy.append(title);
    const summaryText = localized(post.summary);
    if (summaryText) {
      const summary = document.createElement('p');
      summary.className = 'news-item-summary';
      summary.textContent = summaryText;
      copy.append(summary);
    }
    const date = document.createElement('time');
    date.className = 'news-item-date';
    date.dateTime = post.createdAt;
    date.textContent = formatDate(post.createdAt);
    copy.append(date);
    link.append(frame, copy);
    return link;
  }

  async function fetchNews() {
    const response = await fetch(`${apiBase}/news`, { headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error('Unable to load news');
    return response.json();
  }

  async function renderHomeNews() {
    const section = document.getElementById('news');
    if (!section) return;
    const textColumn = document.getElementById('home-news-text');
    const imageColumn = document.getElementById('home-news-images');
    try {
      const posts = await fetchNews();
      const imagePosts = posts.filter((post) => post.imageUrl).slice(0, 2);
      const textPosts = posts.filter((post) => !post.imageUrl).slice(0, 3);
      if (!imagePosts.length && !textPosts.length) return;
      textColumn.replaceChildren(...textPosts.map(makeTextItem));
      imageColumn.replaceChildren(...imagePosts.map((post) => makeImageItem(post)));
      section.hidden = false;
    } catch (error) {
      section.hidden = true;
    }
  }

  async function renderNewsList() {
    const container = document.getElementById('news-archive-list');
    if (!container) return;
    const empty = document.getElementById('news-archive-empty');
    try {
      const posts = await fetchNews();
      const entries = posts.map((post) => {
        const link = document.createElement('a');
        link.className = 'news-archive-item';
        link.href = linkFor(post);
        const copy = document.createElement('div');
        copy.className = 'news-archive-copy';
        const title = document.createElement('h2');
        title.className = 'news-item-title';
        title.textContent = localized(post.title);
        copy.append(title);
        const summaryText = localized(post.summary);
        if (summaryText) {
          const summary = document.createElement('p');
          summary.className = 'news-item-summary';
          summary.textContent = summaryText;
          copy.append(summary);
        }
        const date = document.createElement('time');
        date.className = 'news-item-date';
        date.dateTime = post.createdAt;
        date.textContent = formatDate(post.createdAt);
        copy.append(date);
        link.append(copy);
        if (post.imageUrl) {
          const image = document.createElement('img');
          image.className = 'news-archive-image';
          image.src = post.imageUrl;
          image.alt = localized(post.title);
          image.loading = 'lazy';
          link.append(image);
        }
        return link;
      });
      container.replaceChildren(...entries);
      empty.hidden = posts.length > 0;
    } catch (error) {
      empty.textContent = language() === 'en' ? 'News could not be loaded right now.' : 'Не удалось загрузить новости. Попробуйте позже.';
      empty.hidden = false;
    }
  }

  function appendParagraphs(container, text) {
    const paragraphs = String(text || '').split(/\n\s*\n/).map((part) => part.trim()).filter(Boolean);
    container.replaceChildren(...paragraphs.map((part) => {
      const paragraph = document.createElement('p');
      paragraph.textContent = part;
      return paragraph;
    }));
  }

  async function renderNewsDetail() {
    const container = document.getElementById('news-article');
    if (!container) return;
    const id = new URLSearchParams(location.search).get('id');
    if (!id || !/^\d+$/.test(id)) return showArticleError(container);
    try {
      const response = await fetch(`${apiBase}/news/${encodeURIComponent(id)}`, { headers: { Accept: 'application/json' } });
      if (!response.ok) return showArticleError(container);
      const post = await response.json();
      const article = document.createElement('article');
      const date = document.createElement('time');
      date.className = 'news-article-date';
      date.dateTime = post.createdAt;
      date.textContent = formatDate(post.createdAt);
      const title = document.createElement('h1');
      title.className = 'news-article-title';
      title.textContent = localized(post.title);
      article.append(date, title);
      const summaryText = localized(post.summary);
      if (summaryText) {
        const summary = document.createElement('p');
        summary.className = 'news-article-summary';
        summary.textContent = summaryText;
        article.append(summary);
      }
      if (post.imageUrl) {
        const image = document.createElement('img');
        image.className = 'news-article-image';
        image.src = post.imageUrl;
        image.alt = localized(post.title);
        article.append(image);
      }
      const body = document.createElement('div');
      body.className = 'news-article-content';
      appendParagraphs(body, localized(post.content));
      article.append(body);
      container.replaceChildren(article);
      document.title = `${localized(post.title)} — Enikey`;
    } catch (error) {
      showArticleError(container);
    }
  }

  function showArticleError(container) {
    const message = document.createElement('p');
    message.className = 'news-article-error';
    message.textContent = language() === 'en' ? 'This post is unavailable.' : 'Публикация не найдена или недоступна.';
    container.replaceChildren(message);
  }

  function renderAll() {
    renderHomeNews();
    renderNewsList();
    renderNewsDetail();
  }

  document.addEventListener('DOMContentLoaded', renderAll);
  window.addEventListener('enikey-language-change', renderAll);
})();
