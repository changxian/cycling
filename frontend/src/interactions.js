import { postForm } from './api.js';

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
      key.value = '';
      key.required = false;
      key.placeholder = '留空保留当前密钥';
      key.closest('label').querySelector('.required').textContent = '已保存';
      settingsForm.querySelector('.settings-status').innerHTML = '<span class="status-dot connected"></span>配置已保存';
    } catch (error) { showMessage(message, error.message); }
    finally { button.disabled = false; }
  });
  const form = document.getElementById('ride-form');
  if (!form) return;
  const input = document.getElementById('photo-input');
  const previews = document.getElementById('photo-previews');
  const drop = document.getElementById('drop-zone');
  const photoError = document.getElementById('photo-error');
  const formMessage = document.getElementById('form-message');
  const generateButton = document.getElementById('generate-button');
  const generationStatus = document.getElementById('generation-status');
  let pendingFiles = [];
  let busy = false;
  function updatePhotoCount() {
    document.getElementById('photo-count').textContent = `${previews.children.length} / 8`;
  }
  function addFiles(files) {
    if (busy) return;
    photoError.hidden = true;
    if (previews.children.length + files.length > 8) {
      photoError.textContent = '每次最多上传 8 张照片。';
      photoError.hidden = false;
      return;
    }
    for (const file of files) {
      if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 30 * 1024 * 1024) {
        photoError.textContent = '请选择 30 MB 以内的 JPG、PNG 或 WebP 照片。';
        photoError.hidden = false;
        return;
      }
    }
    for (const file of files) {
      const key = crypto.randomUUID();
      const objectUrl = URL.createObjectURL(file);
      pendingFiles.push({ key, file, objectUrl });
      const preview = document.createElement('div');
      preview.className = 'photo-preview';
      preview.dataset.key = key;
      const image = document.createElement('img');
      image.src = objectUrl;
      image.alt = file.name;
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'remove-photo';
      remove.setAttribute('aria-label', `移除 ${file.name}`);
      remove.title = '移除照片';
      remove.innerHTML = '<i data-lucide="x"></i>';
      preview.append(image, remove);
      previews.append(preview);
    }
    icons();
    updatePhotoCount();
  }
  input.addEventListener('change', () => {
    addFiles(Array.from(input.files));
    input.value = '';
  });
  previews.addEventListener('click', event => {
    const button = event.target.closest('.remove-photo');
    if (!button || busy) return;
    const preview = button.closest('.photo-preview');
    const item = pendingFiles.find(file => file.key === preview.dataset.key);
    if (item) URL.revokeObjectURL(item.objectUrl);
    pendingFiles = pendingFiles.filter(file => file.key !== preview.dataset.key);
    preview.remove();
    updatePhotoCount();
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
    pendingFiles.forEach(({ file }) => data.append('photos', file));
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
