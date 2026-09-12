import { request } from './api.js?v=20260912-photo-preview-1';
import { initInteractions } from './interactions.js?v=20260912-photo-preview-1';
import { navigation, loginView, editorView, settingsView, storySchemesView, galleryView, resultView, errorView } from './views.js?v=20260912-photo-preview-1';

async function start() {
  const main = document.getElementById('main-content');
  const route = window.location.pathname;
  const query = new URLSearchParams(window.location.search);
  let authenticated = false;
  try {
    const session = await request('/api/session');
    authenticated = session.authenticated;
    if (!authenticated && route !== '/login') {
      window.location.replace('/login');
      return;
    }
    if (authenticated && route === '/login') {
      window.location.replace('/');
      return;
    }
    document.body.classList.toggle('login-page', route === '/login');
    document.getElementById('navigation').innerHTML = navigation(authenticated, route);
    if (route === '/login') {
      document.title = '登录 · 骑行时光机';
      main.innerHTML = loginView();
    } else {
      const meta = await request('/api/meta');
      if (route === '/') {
        const edit = query.get('edit');
        const record = edit ? (await request(`/api/rides/${encodeURIComponent(edit)}`)).record : {};
        const journalDate = record.date || meta.today;
        const journal = (await request(`/api/journals/${encodeURIComponent(journalDate)}`)).journal;
        document.title = '记录骑行 · 骑行时光机';
        main.innerHTML = editorView(meta, record, journal);
      } else if (route === '/settings') {
        document.title = 'AI 配置 · 骑行时光机';
        main.innerHTML = settingsView(await request('/api/config'));
      } else if (route === '/story-schemes') {
        document.title = '故事方案配置 · 骑行时光机';
        main.innerHTML = storySchemesView((await request('/api/story-schemes')).story_schemes);
      } else if (route === '/gallery') {
        document.title = '时光画廊 · 骑行时光机';
        main.innerHTML = galleryView(meta, (await request('/api/rides')).items);
      } else if (route === '/generate') {
        const selected = query.get('date');
        const { record } = await request('/api/result' + (selected ? `?date=${encodeURIComponent(selected)}` : ''));
        if (!record) { window.location.replace('/'); return; }
        document.title = `${record.title} · 骑行时光机`;
        main.innerHTML = resultView(meta, record);
      } else {
        main.innerHTML = errorView('没有找到这个页面。');
      }
    }
  } catch (error) {
    document.getElementById('navigation').innerHTML = navigation(authenticated, route);
    main.innerHTML = errorView(error.message);
  } finally {
    main.setAttribute('aria-busy', 'false');
    initInteractions();
  }
}

start();
