import { postForm, request } from './api.js?v=20260913-accounts-1';
import { collectPhotoFiles } from './photo-files.js?v=20260913-accounts-1';

export function initInteractions() {
  const icons = () => window.lucide?.createIcons();
  icons();
  const showMessage = (element, text, success = false) => {
    element.textContent = text;
    element.className = `notice ${success ? 'success' : 'error'}`;
    element.hidden = false;
  };
  const loginForm = document.getElementById('login-form') || document.getElementById('register-form');
  loginForm?.addEventListener('submit', async event => {
    event.preventDefault();
    const button = loginForm.querySelector('button[type="submit"]');
    button.disabled = true;
    try {
      await postForm(loginForm.action, new FormData(loginForm));
      window.location.assign('/');
    } catch (error) {
      showMessage(loginForm.querySelector('[role="alert"]'), error.message);
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
  const photoCarousel = document.querySelector('.photo-carousel');
  const previewUrls = new Map();
  const loadedJournalDate = form.elements.date.value;
  function refreshPhotoCount() {
    document.getElementById('photo-count').textContent = `${photoCarousel.querySelectorAll('.carousel-slide').length} 张`;
  }
  function updatePendingPreviews(activeIndex) {
    for (const [file, url] of previewUrls) {
      if (!pendingFiles.includes(file)) {
        URL.revokeObjectURL(url);
        previewUrls.delete(file);
      }
    }
    photoCarousel.querySelectorAll('[data-pending-index]').forEach(slide => slide.remove());
    const track = photoCarousel.querySelector('.carousel-track');
    pendingFiles.forEach((file, index) => {
      if (!previewUrls.has(file)) previewUrls.set(file, URL.createObjectURL(file));
      const slide = document.createElement('div');
      slide.className = 'carousel-slide';
      slide.dataset.pendingIndex = String(index);
      const image = document.createElement('img');
      image.alt = `待保存照片：${file.name}`;
      const label = document.createElement('span');
      label.className = 'pending-photo-label';
      label.textContent = `待保存 · ${file.name}`;
      image.addEventListener('error', () => {
        image.hidden = true;
        label.textContent = `待保存 · ${file.name} · 浏览器无法预览此格式，保存后可查看`;
      });
      image.src = previewUrls.get(file);
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'remove-photo remove-pending-photo';
      remove.dataset.index = String(index);
      remove.setAttribute('aria-label', `移除待上传图片：${file.name}`);
      remove.textContent = '×';
      slide.append(image, label, remove);
      track.append(slide);
    });
    photoCarousel.dispatchEvent(new CustomEvent('carousel-update', { detail: { index: activeIndex } }));
    refreshPhotoCount();
  }
  function removePendingPhoto(index) {
    if (busy || !Number.isInteger(index) || index < 0 || index >= pendingFiles.length) return;
    const slides = Array.from(photoCarousel.querySelectorAll('.carousel-slide'));
    const activeIndex = slides.findIndex(slide => slide.classList.contains('is-active'));
    const removedIndex = slides.findIndex(slide => Number(slide.dataset.pendingIndex) === index);
    pendingFiles.splice(index, 1);
    updatePendingPhotoNames();
    updatePendingPreviews(activeIndex - (removedIndex < activeIndex ? 1 : 0));
    showMessage(journalMessage, `已选择 ${pendingFiles.length} 张照片，点击“保存本次记录”后入库。`, true);
  }
  function updatePendingPhotoNames() {
    pendingPhotoNames.replaceChildren(...pendingFiles.map((file, index) => {
      const item = document.createElement('li');
      const name = document.createElement('span');
      name.textContent = file.name;
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'remove-pending-photo';
      remove.dataset.index = String(index);
      remove.setAttribute('aria-label', `移除待上传图片：${file.name}`);
      remove.textContent = '移除';
      item.append(name, remove);
      return item;
    }));
  }
  function addFiles(files) {
    if (busy) return;
    if (!files.length) return;
    photoError.hidden = true;
    const result = collectPhotoFiles(pendingFiles, files);
    if (result.error) {
      photoError.textContent = result.error;
      photoError.hidden = false;
      return;
    }
    const activeIndex = photoCarousel.querySelectorAll('.carousel-slide').length;
    pendingFiles = result.files;
    updatePendingPhotoNames();
    updatePendingPreviews(activeIndex);
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
  pendingPhotoNames.addEventListener('click', event => {
    const button = event.target.closest('.remove-pending-photo');
    if (!button || busy) return;
    removePendingPhoto(Number(button.dataset.index));
  });
  document.querySelectorAll('[data-carousel]').forEach(carousel => {
    let slides = Array.from(carousel.querySelectorAll('.carousel-slide'));
    let index = 0;
    let timer;
    if (!carousel.querySelector('.carousel-track')) {
      const track = document.createElement('div');
      track.className = 'carousel-track';
      carousel.prepend(track);
    }
    if (!carousel.querySelector('.carousel-count')) {
      for (const [direction, label, symbol] of [['prev', '上一张', '‹'], ['next', '下一张', '›']]) {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `carousel-arrow ${direction === 'prev' ? 'previous' : 'next'}`;
        button.dataset[direction === 'prev' ? 'carouselPrev' : 'carouselNext'] = '';
        button.setAttribute('aria-label', label);
        button.textContent = symbol;
        carousel.append(button);
      }
      const count = document.createElement('span');
      count.className = 'carousel-count';
      carousel.append(count);
    }
    if (!carousel.querySelector('.carousel-empty')) {
      const empty = document.createElement('p');
      empty.className = 'carousel-empty';
      empty.textContent = '暂无记录，可以继续添加。';
      carousel.append(empty);
    }
    const count = carousel.querySelector('.carousel-count');
    const show = next => {
      slides = Array.from(carousel.querySelectorAll('.carousel-slide'));
      carousel.querySelector('.carousel-empty').hidden = slides.length > 0;
      carousel.querySelector('.carousel-track').hidden = !slides.length;
      carousel.querySelectorAll('.carousel-arrow, .carousel-count, .remove-text').forEach(control => {
        control.hidden = !slides.length;
      });
      if (!slides.length) {
        clearInterval(timer);
        index = 0;
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
    const groupPhotoCount = groupId => document.querySelectorAll(`.photo-carousel .carousel-slide[data-group-id="${CSS.escape(groupId)}"]`).length;
    const groupHasText = groupId => document.querySelectorAll(`#text-carousel .carousel-slide[data-group-id="${CSS.escape(groupId)}"]`).length > 0;
    const journalApi = `/api/journals/${encodeURIComponent(loadedJournalDate)}`;
    function refreshCarousels() {
      document.querySelectorAll('[data-carousel]').forEach(item => item.dispatchEvent(new CustomEvent('carousel-update')));
      refreshPhotoCount();
    }
    function removeGroupFromPage(groupId) {
      document.querySelectorAll(`.carousel-slide[data-group-id="${CSS.escape(groupId)}"]`).forEach(slide => slide.remove());
      if (document.getElementById('edit-group-id').value === groupId) cancelTextEdit.click();
      refreshCarousels();
    }
    async function deletePhoto(slide) {
      const removeBtn = slide.querySelector('.remove-photo');
      const groupId = removeBtn.dataset.groupId;
      const photoName = removeBtn.dataset.photo;
      if (groupPhotoCount(groupId) > 1) {
        if (!window.confirm('确认从当天手记中删除这张图片？已生成故事中的图片不会改变。')) return;
        await request(`${journalApi}/photo/${encodeURIComponent(groupId)}/${encodeURIComponent(photoName)}`, { method: 'DELETE' });
        slide.remove();
        show(index);
        refreshPhotoCount();
        showMessage(journalMessage, '已删除并保存，可继续记录。', true);
        return;
      }
      if (groupHasText(groupId)) {
        const alsoDeleteText = window.confirm('这是该组最后一张图片。删除后对应文案也会一并删除，是否确认？');
        if (alsoDeleteText) {
          await request(`${journalApi}/group/${encodeURIComponent(groupId)}`, { method: 'DELETE' });
          removeGroupFromPage(groupId);
        } else {
          await request(`${journalApi}/photo/${encodeURIComponent(groupId)}/${encodeURIComponent(photoName)}`, { method: 'DELETE' });
          slide.remove();
          refreshCarousels();
        }
        showMessage(journalMessage, '已删除并保存，可继续记录。', true);
        return;
      }
      if (!window.confirm('确认从当天手记中删除这张图片？已生成故事中的图片不会改变。')) return;
      await request(`${journalApi}/photo/${encodeURIComponent(groupId)}/${encodeURIComponent(photoName)}`, { method: 'DELETE' });
      slide.remove();
      show(index);
      refreshPhotoCount();
      showMessage(journalMessage, '已删除并保存，可继续记录。', true);
    }
    async function deleteTextGroup() {
      const activeCard = carousel.querySelector('.carousel-slide.is-active');
      const groupId = activeCard?.dataset.groupId;
      if (!groupId) return;
      if (!window.confirm('确认删除这条文字记录？该组对应的图片也会一并删除，删除后无法恢复。')) return;
      await request(`${journalApi}/group/${encodeURIComponent(groupId)}`, { method: 'DELETE' });
      removeGroupFromPage(groupId);
      showMessage(journalMessage, '已删除并保存，可继续记录。', true);
    }
    carousel.addEventListener('click', async event => {
      const remove = event.target.closest('.remove-photo, .remove-text');
      if (!remove || busy) return;
      event.stopPropagation();
      if (remove.classList.contains('remove-pending-photo')) {
        removePendingPhoto(Number(remove.dataset.index));
        return;
      }
      busy = true;
      clearInterval(timer);
      try {
        if (remove.classList.contains('remove-photo')) {
          const slide = remove.closest('.carousel-slide');
          if (!slide) return;
          await deletePhoto(slide);
        } else {
          await deleteTextGroup();
        }
      } catch (error) { showMessage(journalMessage, error.message); }
      finally { busy = false; refreshCarousels(); }
    });
    carousel.querySelector('[data-carousel-prev]')?.addEventListener('click', () => show(index - 1));
    carousel.querySelector('[data-carousel-next]')?.addEventListener('click', () => show(index + 1));
    const startTimer = () => {
      clearInterval(timer);
      if (!busy && !carousel.matches(':hover') && !matchMedia('(prefers-reduced-motion: reduce)').matches && slides.length > 1) {
        timer = setInterval(() => show(index + 1), 5000);
      }
    };
    carousel.addEventListener('carousel-update', event => {
      const length = carousel.querySelectorAll('.carousel-slide').length;
      show(Math.max(0, Math.min(event.detail?.index ?? index, length - 1)));
      startTimer();
    });
    carousel.addEventListener('pointerenter', () => clearInterval(timer));
    carousel.addEventListener('pointerleave', startTimer);
    show(0);
    startTimer();
    window.addEventListener('pagehide', () => clearInterval(timer));
    window.addEventListener('pageshow', startTimer);
  });
  window.addEventListener('pagehide', event => {
    if (event.persisted) return;
    previewUrls.forEach(url => URL.revokeObjectURL(url));
    previewUrls.clear();
  });
  journalText?.addEventListener('input', () => {
    document.getElementById('text-length').textContent = `${journalText.value.length} / 1024`;
  });
  document.getElementById('text-carousel')?.addEventListener('click', event => {
    const card = event.target.closest('[data-group-id]');
    if (!card || card.classList.contains('remove-text')) return;
    journalText.value = card.dataset.text || '';
    document.getElementById('edit-group-id').value = card.dataset.groupId;
    document.getElementById('text-length').textContent = `${journalText.value.length} / 1024`;
    cancelTextEdit.hidden = false;
    journalText.focus();
  });
  cancelTextEdit?.addEventListener('click', () => {
    journalText.value = '';
    document.getElementById('edit-group-id').value = '';
    document.getElementById('text-length').textContent = '0 / 1024';
    cancelTextEdit.hidden = true;
    journalText.focus();
  });
  journalSave?.addEventListener('click', async () => {
    if (busy) return;
    const data = new FormData();
    data.append('date', form.elements.date.value);
    data.append('text', journalText.value);
    data.append('edit_group_id', document.getElementById('edit-group-id').value);
    data.append('background_music', document.getElementById('background-music').checked ? '1' : '0');
    pendingFiles.forEach(file => data.append('photos', file));
    if (!journalText.value.trim() && !pendingFiles.length) { showMessage(journalMessage, '先写下一段经历，或选择照片。'); return; }
    journalSave.disabled = true;
    busy = true;
    try {
      await postForm('/api/journals', data);
      // Keep the user in the same editor. Reloading refreshes the saved
      // carousel without turning this action into a navigation step.
      window.location.reload();
    } catch (error) { showMessage(journalMessage, error.message); }
    finally { journalSave.disabled = false; busy = false; }
  });
  const waitForStoryTask = taskId => new Promise((resolve, reject) => {
    let elapsed = 0;
    const step = () => {
      request('/api/story-tasks/' + encodeURIComponent(taskId))
        .then(result => {
          const task = result.task;
          if (task.status === 'done' || task.status === 'failed') { resolve(task); return; }
          const label = generationStatus.childNodes[generationStatus.childNodes.length - 1];
          if (label && label.nodeType === 3) label.textContent = '正在逐张创作故事 ' + task.done + ' / ' + task.total + '…';
          elapsed += 1500;
          setTimeout(step, 1500);
        })
        .catch(error => {
          if (elapsed < 60000) {
            setTimeout(step, 1500);
          } else {
            reject(error instanceof Error ? error : new Error(String((error && error.message) || error)));
          }
        });
    };
    step();
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
      if (result.task) {
        const done = await waitForStoryTask(result.task.task_id);
        if (done.status === 'failed') {
          throw new Error(done.error || '骑行故事创建失败，请稍后重试。');
        }
        window.location.assign('/generate?date=' + result.task.date);
        return;
      }
      window.location.assign(result.redirect);
    } catch (error) {
      showMessage(formMessage, error.message === '网络连接中断，请检查连接后重试。' ? '网络连接中断，表单已保留，请重试。' : error.message);
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
