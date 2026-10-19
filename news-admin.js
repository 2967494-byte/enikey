(() => {
  const apiBase = (window.API_CONFIG?.BASE_URL || '/api').replace(/\/$/, '');
  const loginSection = document.getElementById('admin-login');
  const workspace = document.getElementById('admin-workspace');
  const form = document.getElementById('post-form');
  const postList = document.getElementById('admin-post-list');
  const imageInput = document.getElementById('image-file');
  const imageUrlInput = document.getElementById('image-url');
  const imagePreview = document.getElementById('image-preview');
  const imagePreviewWrap = document.getElementById('image-preview-wrap');
  let posts = [];
  let removeImage = false;

  async function request(path, options = {}) {
    const response = await fetch(`${apiBase}${path}`, {
      credentials: 'include',
      ...options,
      headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) }
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || 'Не удалось выполнить запрос');
    return payload;
  }

  function setMessage(element, message) {
    element.textContent = message;
  }

  function formatDate(value) {
    const date = new Date(`${value.replace(' ', 'T')}Z`);
    if (Number.isNaN(date.getTime())) return '';
    return new Intl.DateTimeFormat('ru-RU', {
      day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Europe/Moscow'
    }).format(date);
  }

  function setAuthenticated(authenticated) {
    loginSection.hidden = authenticated;
    workspace.hidden = !authenticated;
  }

  function addPostCard(post) {
    const card = document.createElement('article');
    card.className = 'admin-post-card';
    const copy = document.createElement('div');
    const title = document.createElement('h3');
    title.textContent = post.title.ru;
    const date = document.createElement('p');
    date.textContent = formatDate(post.createdAt);
    const status = document.createElement('span');
    status.className = `admin-post-status${post.isPublished ? ' is-published' : ''}`;
    status.textContent = post.isPublished ? 'Опубликовано' : 'Черновик';
    copy.append(title, date, status);
    const actions = document.createElement('div');
    actions.className = 'admin-post-actions';
    const edit = document.createElement('button');
    edit.type = 'button';
    edit.className = 'post-action-button';
    edit.textContent = 'Изменить';
    edit.addEventListener('click', () => populateForm(post));
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'post-action-button';
    remove.textContent = 'Удалить';
    remove.addEventListener('click', () => deletePost(post));
    actions.append(edit, remove);
    card.append(copy, actions);
    return card;
  }

  function renderPosts() {
    postList.replaceChildren(...posts.map(addPostCard));
    document.getElementById('post-count').textContent = String(posts.length);
    document.getElementById('admin-empty').hidden = posts.length > 0;
  }

  async function loadPosts() {
    posts = await request('/admin/news');
    renderPosts();
  }

  async function openWorkspace() {
    setAuthenticated(true);
    try {
      await loadPosts();
    } catch (error) {
      setAuthenticated(false);
      setMessage(document.getElementById('login-message'), error.message);
    }
  }

  function resetForm() {
    form.reset();
    document.getElementById('post-id').value = '';
    imageUrlInput.value = '';
    imageInput.value = '';
    removeImage = false;
    imagePreviewWrap.hidden = true;
    document.getElementById('form-title').textContent = 'Новая публикация';
    document.getElementById('save-button').textContent = 'Сохранить черновик';
    document.getElementById('cancel-edit-button').hidden = true;
    setMessage(document.getElementById('form-message'), '');
  }

  function populateForm(post) {
    document.getElementById('post-id').value = post.id;
    document.getElementById('title-ru').value = post.title.ru || '';
    document.getElementById('title-en').value = post.title.en === post.title.ru ? '' : post.title.en || '';
    document.getElementById('summary-ru').value = post.summary.ru || '';
    document.getElementById('summary-en').value = post.summary.en === post.summary.ru ? '' : post.summary.en || '';
    document.getElementById('content-ru').value = post.content.ru || '';
    document.getElementById('content-en').value = post.content.en === post.content.ru ? '' : post.content.en || '';
    document.getElementById('is-published').checked = post.isPublished;
    imageUrlInput.value = post.imageUrl || '';
    imageInput.value = '';
    removeImage = false;
    imagePreviewWrap.hidden = !post.imageUrl;
    if (post.imageUrl) imagePreview.src = post.imageUrl;
    document.getElementById('form-title').textContent = 'Редактировать публикацию';
    document.getElementById('save-button').textContent = post.isPublished ? 'Сохранить изменения' : 'Сохранить черновик';
    document.getElementById('cancel-edit-button').hidden = false;
    setMessage(document.getElementById('form-message'), '');
    form.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function imageToDataUrl(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(new Error('Не удалось прочитать изображение'));
      reader.readAsDataURL(file);
    });
  }

  async function uploadSelectedImage() {
    const file = imageInput.files[0];
    if (!file) return imageUrlInput.value;
    if (file.size > 5 * 1024 * 1024) throw new Error('Изображение должно быть не больше 5 МБ');
    const imageData = await imageToDataUrl(file);
    const result = await request('/admin/upload', { method: 'POST', body: JSON.stringify({ imageData }) });
    return result.imageUrl;
  }

  async function savePost(event) {
    event.preventDefault();
    const message = document.getElementById('form-message');
    const saveButton = document.getElementById('save-button');
    saveButton.disabled = true;
    setMessage(message, 'Сохраняем…');
    try {
      let imageUrl = removeImage ? '' : imageUrlInput.value;
      imageUrl = await uploadSelectedImage() || imageUrl;
      const payload = {
        titleRu: document.getElementById('title-ru').value,
        titleEn: document.getElementById('title-en').value,
        summaryRu: document.getElementById('summary-ru').value,
        summaryEn: document.getElementById('summary-en').value,
        contentRu: document.getElementById('content-ru').value,
        contentEn: document.getElementById('content-en').value,
        imageUrl,
        isPublished: document.getElementById('is-published').checked
      };
      const id = document.getElementById('post-id').value;
      await request(id ? `/admin/news/${encodeURIComponent(id)}` : '/admin/news', {
        method: id ? 'PUT' : 'POST', body: JSON.stringify(payload)
      });
      resetForm();
      await loadPosts();
      setMessage(message, 'Публикация сохранена.');
    } catch (error) {
      setMessage(message, error.message);
    } finally {
      saveButton.disabled = false;
    }
  }

  async function deletePost(post) {
    if (!window.confirm(`Удалить публикацию «${post.title.ru}»?`)) return;
    try {
      await request(`/admin/news/${encodeURIComponent(post.id)}`, { method: 'DELETE' });
      if (document.getElementById('post-id').value === String(post.id)) resetForm();
      await loadPosts();
    } catch (error) {
      window.alert(error.message);
    }
  }

  document.getElementById('login-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const message = document.getElementById('login-message');
    setMessage(message, '');
    try {
      await request('/admin/login', {
        method: 'POST', body: JSON.stringify({ password: document.getElementById('admin-password').value })
      });
      document.getElementById('admin-password').value = '';
      await openWorkspace();
    } catch (error) {
      setMessage(message, error.message);
    }
  });

  form.addEventListener('submit', savePost);
  document.getElementById('new-post-button').addEventListener('click', resetForm);
  document.getElementById('cancel-edit-button').addEventListener('click', resetForm);
  document.getElementById('is-published').addEventListener('change', (event) => {
    const button = document.getElementById('save-button');
    button.textContent = event.target.checked ? 'Опубликовать' : 'Сохранить черновик';
  });
  imageInput.addEventListener('change', () => {
    const file = imageInput.files[0];
    if (!file) return;
    removeImage = false;
    imagePreview.src = URL.createObjectURL(file);
    imagePreviewWrap.hidden = false;
  });
  document.getElementById('remove-image-button').addEventListener('click', () => {
    imageInput.value = '';
    imageUrlInput.value = '';
    removeImage = true;
    imagePreviewWrap.hidden = true;
  });
  document.getElementById('logout-button').addEventListener('click', async () => {
    try { await request('/admin/logout', { method: 'POST', body: '{}' }); } catch (error) {}
    posts = [];
    renderPosts();
    resetForm();
    setAuthenticated(false);
  });

  request('/admin/session').then((session) => {
    if (session.authenticated) openWorkspace();
    else setAuthenticated(false);
  }).catch(() => {
    setAuthenticated(false);
    setMessage(document.getElementById('login-message'), 'Сервер новостей недоступен.');
  });
})();
