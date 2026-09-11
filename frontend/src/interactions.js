import { postForm, request } from './api.js';

export function initInteractions() {
  const icons = () => window.lucide?.createIcons();
  icons();
  const showMessage = (element, text, success = false) => {
    element.textContent = text;
    element.className = `notice ${success ? 'success' : 'error'}`;
    element.hidden = false;
  };
  const loginForm = document.getElementById('login-form');
  loginForm?.addEventListener('submit', async event => {
    event.preventDefault();
    const button = loginForm.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await postForm('/api/login', new FormData(loginForm));
      window.location.assign('/');
    } catch (error) {
      showMessage(document.getElementById('login-message'), error.message);
    } finally { button.disabled = false; }
  });
  const logoutForm = document.querySelector('.logout-form');
  logoutForm?.addEventListener('submit', async event => {
    event.preventDefault();
    const button = logoutForm.querySelector('button');
    button.disabled = true;
    try {
      await postForm('/api/logout');
      window.location.replace('/login');
    } catch (error) {
      let message = document.getElementById('logout-message');
      if (!message) {
        message = document.createElement('div');
        message.id = 'logout-message';
        message.setAttribute('role', 'alert');
        document.getElementById('main-content').prepend(message);
      }
      showMessage(message, error.message);
    } finally { button.disabled = false; }
  });
  document.querySelectorAll('.password-toggle').forEach(button => {
    button.addEventListener('click', () => {
      const input = document.getElementById(button.dataset.target);
      if (input.dataset.masked === 'true') {
        input.dataset.masked = 'false';
        input.readOnly = false;
        input.removeAttribute('value');
        input.value = '';
        input.name = 'api_key';
        input.placeholder = '请输入新的 API Key';
        input.required = true;
        button.setAttribute('aria-label', '显示密钥');
        button.title = '显示密钥';
        button.innerHTML = '<i data-lucide="eye"></i>';
        icons();
        input.focus();
        return;
      }
      input.type = input.type === 'password' ? 'text' : 'password';
      const label = input.type === 'password' ? '显示密码' : '隐藏密码';
      button.setAttribute('aria-label', label);
      button.title = label;
      button.innerHTML = `<i data-lucide="${input.type === 'password' ? 'eye' : 'eye-off'}"></i>`;
      icons();
    });
  });
  const settingsForm = document.getElementById('settings-form');
  settingsForm?.addEventListener('submit', async event => {
    event.preventDefault();
    const button = settingsForm.querySelector('button[type="submit"]');
    const message = document.getElementById('settings-message');
    button.disabled = true;
    message.hidden = true;
    try {
      const result = await postForm(settingsForm.action, new FormData(settingsForm));
      showMessage(message, result.message, true);
      const key = document.getElementById('api-key');
      key.value = key.dataset.maskedValue || '';
      key.removeAttribute('name');
      key.readOnly = true;
      key.dataset.masked = 'true';
      key.required = false;
      key.placeholder = '';
      key.closest('label').querySelector('.required').textContent = '已保存';
      settingsForm.querySelector('.settings-status').innerHTML = '<span class="status-dot connected"></span>配置已保存';
    } catch (error) { showMessage(message, error.message); }
    finally { button.disabled = false; }
  });
  const storySchemesForm = document.getElementById('story-schemes-form');
  const schemeStyle = document.getElementById('story-scheme-style');
  const updateSchemeList = () => document.querySelectorAll('[data-scheme-list]').forEach(list => {
    list.hidden = list.dataset.schemeList !== schemeStyle?.value;
  });
  schemeStyle?.addEventListener('change', updateSchemeList);
  updateSchemeList();
  storySchemesForm?.addEventListener('submit', async event => {
    event.preventDefault();
    const button = storySchemesForm.querySelector('button[type="submit"]');
    const message = document.getElementById('story-schemes-message');
    button.disabled = true;
    message.hidden = true;
    try {
      const result = await postForm(storySchemesForm.action, new FormData(storySchemesForm));
      showMessage(message, result.message, true);
      storySchemesForm.querySelector('textarea[name="scheme_text"]').value = '';
      window.setTimeout(() => window.location.reload(), 300);
    } catch (error) { showMessage(message, error.message); }
    finally { button.disabled = false; }
  });
  document.querySelectorAll('.delete-scheme').forEach(button => {
    button.addEventListener('click', async () => {
      if (!window.confirm('确定删除这条故事方案吗？此操作无法撤销。')) return;
      button.disabled = true;
      try {
        await request(`/api/story-schemes/${encodeURIComponent(button.dataset.schemeId)}`, { method: 'DELETE' });
        window.location.reload();
      } catch (error) {
        const message = document.getElementById('story-schemes-message');
        if (message) showMessage(message, error.message);
        button.disabled = false;
      }
    });
  });
  const form = document.getElementById('ride-form');
  if (!form) return;
  const input = document.getElementById('photo-input');
  const drop = document.getElementById('drop-zone');
  const photoError = document.getElementById('photo-error');
  const formMessage = document.getElementById('form-message');
  const generateButton = document.getElementById('generate-button');
  const generationStatus = document.getElementById('generation-status');
  const journalText = document.getElementById('journal-text');
  const journalSave = document.getElementById('save-journal');
  const journalMessage = document.getElementById('journal-message');
  const pendingPhotoNames = document.getElementById('pending-photo-names');
  const cancelTextEdit = document.getElementById('cancel-text-edit');
  let pendingFiles = [];
  let busy = false;
  const loadedJournalDate = form.elements.date.value;
  function updatePendingPhotoNames() {
    pendingPhotoNames.replaceChildren(...pendingFiles.map(file => {
      const item = document.createElement('li');
      item.textContent = file.name;
      return item;
    }));
  }
  function addFiles(files) {
    if (busy) return;
    photoError.hidden = true;
    for (const file of files) {
      if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
        photoError.textContent = '请选择 JPG、PNG 或 WebP 格式的照片。';
        photoError.hidden = false;
        return;
      }
    }
    for (const file of files) {
      pendingFiles.push(file);
    }
    updatePendingPhotoNames();
    document.getElementById('photo-count').textContent = `${document.querySelectorAll('.photo-carousel .carousel-slide').length + pendingFiles.length} 张`;
    showMessage(journalMessage, `已选择 ${pendingFiles.length} 张照片，点击“保存本次记录”后入库。`, true);
  }
  input.addEventListener('change', () => {
    addFiles(Array.from(input.files));
    input.value = '';
  });
  ['dragenter', 'dragover'].forEach(name => drop.addEventListener(name, event => {
    event.preventDefault();
    drop.classList.add('dragging');
  }));
  ['dragleave', 'drop'].forEach(name => drop.addEventListener(name, event => {
    event.preventDefault();
    drop.classList.remove('dragging');
  }));
  drop.addEventListener('drop', event => addFiles(Array.from(event.dataTransfer.files)));
  document.querySelectorAll('[data-carousel]').forEach(carousel => {
    let slides = Array.from(carousel.querySelectorAll('.carousel-slide'));
    if (!slides.length) return;
    let index = 0;
    let timer;
    const count = carousel.querySelector('.carousel-count');
    const show = next => {
      slides = Array.from(carousel.querySelectorAll('.carousel-slide'));
      if (!slides.length) {
        clearInterval(timer);
        carousel.replaceChildren();
        const empty = document.createElement('p');
        empty.className = 'carousel-empty';
        empty.textContent = '暂无记录，可以继续添加。';
        carousel.append(empty);
        return;
      }
      index = (next + slides.length) % slides.length;
      slides.forEach((slide, i) => slide.classList.toggle('is-active', i === index));
      if (count) count.textContent = `${index + 1} / ${slides.length}`;
    };
    if (carousel.id === 'text-carousel') {
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'remove-text delete-scheme';
      remove.textContent = '删除本条文字';
      carousel.append(remove);
    }
    carousel.addEventListener('click', async event => {
      const remove = event.target.closest('.remove-photo, .remove-text');
      if (!remove || busy) return;
      event.stopPropagation();
      const slide = remove.closest('.carousel-slide') || carousel.querySelector('.carousel-slide.is-active');
      if (!slide) return;
      const isPhoto = remove.classList.contains('remove-photo');
      if (!window.confirm(isPhoto ? '确认从当天手记中删除这张图片？已生成故事中的图片不会改变。' : '确认删除这条文字记录？删除后无法恢复。')) return;
      busy = true;
      remove.disabled = true;
      clearInterval(timer);
      try {
        const id = isPhoto ? slide.dataset.retained : slide.dataset.textId;
        await request(`/api/journals/${encodeURIComponent(loadedJournalDate)}/${isPhoto ? 'photos' : 'texts'}/${encodeURIComponent(id)}`, { method: 'DELETE' });
        if (!isPhoto && document.getElementById('edit-text-id').value === id) cancelTextEdit.click();
        slide.remove();
        show(index);
        document.getElementById('photo-count').textContent = `${document.querySelectorAll('.photo-carousel .carousel-slide').length + pendingFiles.length} 张`;
        showMessage(journalMessage, '已删除并保存，可继续记录。', true);
      } catch (error) { showMessage(journalMessage, error.message); }
      finally { busy = false; remove.disabled = false; }
    });
    carousel.querySelector('[data-carousel-prev]')?.addEventListener('click', () => show(index - 1));
    carousel.querySelector('[data-carousel-next]')?.addEventListener('click', () => show(index + 1));
    if (!matchMedia('(prefers-reduced-motion: reduce)').matches && slides.length > 1) {
      timer = setInterval(() => show(index + 1), 5000);
      carousel.addEventListener('pointerenter', () => clearInterval(timer));
      carousel.addEventListener('pointerleave', () => { timer = setInterval(() => show(index + 1), 5000); });
    }
  });
  journalText?.addEventListener('input', () => {
    document.getElementById('text-length').textContent = `${journalText.value.length} / 1024`;
  });
  document.getElementById('text-carousel')?.addEventListener('click', event => {
    const card = event.target.closest('[data-text-id]');
    if (!card) return;
    journalText.value = card.dataset.text || '';
    document.getElementById('edit-text-id').value = card.dataset.textId;
    document.getElementById('text-length').textContent = `${journalText.value.length} / 1024`;
    cancelTextEdit.hidden = false;
    journalText.focus();
  });
  cancelTextEdit?.addEventListener('click', () => {
    journalText.value = '';
    document.getElementById('edit-text-id').value = '';
    document.getElementById('text-length').textContent = '0 / 1024';
    cancelTextEdit.hidden = true;
    journalText.focus();
  });
  journalSave?.addEventListener('click', async () => {
    if (busy) return;
    const data = new FormData();
    data.append('date', form.elements.date.value);
    data.append('text', journalText.value);
    data.append('edit_text_id', document.getElementById('edit-text-id').value);
    data.append('background_music', document.getElementById('background-music').checked ? '1' : '0');
    document.querySelectorAll('.photo-carousel [data-retained]').forEach(item => data.append('retained_photos', item.dataset.retained));
    pendingFiles.forEach(file => data.append('photos', file));
    if (!journalText.value.trim() && !pendingFiles.length) { showMessage(journalMessage, '先写下一段经历，或选择照片。'); return; }
    journalSave.disabled = true;
    try {
      await postForm('/api/journals', data);
      // Keep the user in the same editor. Reloading refreshes the saved
      // carousel without turning this action into a navigation step.
      window.location.reload();
    } catch (error) { showMessage(journalMessage, error.message); }
    finally { journalSave.disabled = false; }
  });
  const styleInputs = Array.from(form.querySelectorAll('input[name="styles"]'));
  function updateStyles() {
    const count = styleInputs.filter(input => input.checked).length;
    document.getElementById('selection-count').textContent = count ? `已选择 ${count} 种文案风格` : '选择属于这一程的文案风格';
  }
  styleInputs.forEach(input => input.addEventListener('change', updateStyles));
  updateStyles();
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy) return;
    formMessage.hidden = true;
    if (!styleInputs.some(input => input.checked)) {
      showMessage(formMessage, '请至少选择一种文案风格。');
      styleInputs[0].focus();
      return;
    }
    const data = new FormData(form);
    data.delete('photos');
    pendingFiles.forEach(file => data.append('photos', file));
    document.querySelectorAll('.photo-carousel [data-retained]').forEach(item => data.append('retained_photos', item.dataset.retained));
    data.set('background_music', document.getElementById('background-music').checked ? '1' : '0');
    busy = true;
    form.setAttribute('aria-busy', 'true');
    const controls = Array.from(form.querySelectorAll('input, button'));
    controls.forEach(control => control.disabled = true);
    generateButton.querySelector('span').textContent = '正在生成…';
    generationStatus.hidden = false;
    try {
      const result = await postForm(form.action, data);
      window.location.assign(result.redirect);
    } catch (error) {
      showMessage(formMessage, error.message === 'Failed to fetch' ? '网络连接中断，表单已保留，请重试。' : error.message);
      formMessage.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } finally {
      busy = false;
      form.removeAttribute('aria-busy');
      controls.forEach(control => control.disabled = false);
      generateButton.querySelector('span').textContent = '生成骑行故事';
      generationStatus.hidden = true;
    }
  });
}
