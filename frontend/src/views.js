export const escapeHtml = (value = '') => String(value ?? '').replace(/[&<>"']/g, char => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[char]));
const e = escapeHtml;
const icon = name => `<i data-lucide="${e(name)}"></i>`;
const displayDate = date => e(date).replaceAll('-', ' / ');
const photoUrl = name => `/tmp/thumbs/${encodeURIComponent(name)}.jpg`;

export function navigation(authenticated, route) {
  const links = [['/', 'circle-plus', '记录骑行'], ['/gallery', 'images', '时光画廊'], ['/settings', 'sliders-horizontal', 'AI 配置'], ['/story-schemes', 'book-open', '故事方案']];
  return `<a class="brand" href="/"><span class="brand-icon">${icon('bike')}</span><span>骑行时光机<small>CYCLING JOURNAL</small></span></a>
    ${authenticated ? `<nav aria-label="主导航">${links.map(([href, name, label]) => `<a href="${href}" ${route === href ? 'aria-current="page"' : ''}>${icon(name)}<span>${label}</span></a>`).join('')}</nav>
      <form action="/api/logout" method="post" class="logout-form"><button class="icon-button" aria-label="退出登录" title="退出登录">${icon('log-out')}</button></form>`
      : '<span class="nav-note">每一程，都值得被记住。</span>'}`;
}

export function loginView() {
  return `<div class="login-layout"><section class="login-form-section">
    <div class="eyebrow"><span></span> YOUR NEXT CHAPTER</div><h1>骑行时光机</h1><p class="lead">回来，续写你的骑行故事。</p>
    <form action="/api/login" method="post" class="login-form" id="login-form">
      <div class="notice error" id="login-message" role="alert" hidden></div>
      <label>账号<input name="username" autocomplete="username" required placeholder="请输入账号" autofocus></label>
      <label>密码<span class="password-field"><input type="password" name="password" id="login-password" autocomplete="current-password" required placeholder="请输入密码"><button type="button" class="icon-button password-toggle" data-target="login-password" aria-label="显示密码" title="显示密码">${icon('eye')}</button></span></label>
      <button class="button primary full" type="submit">登录 ${icon('arrow-right')}</button>
    </form><span class="login-footnote">${icon('lock-keyhole')} 私人骑行手记</span></section>
    <div class="login-photo"><img src="/assets/cycling.jpg" alt="骑行者穿过松林与群山之间的公路"><div class="photo-caption"><span>ON THE ROAD</span><p>风景在路上，<br>故事在脚下。</p></div><a class="photo-credit" href="https://unsplash.com/photos/rCeH116HQAo" target="_blank" rel="noopener noreferrer">摄影：Kirsten Frank / Unsplash</a></div></div>`;
}

export function editorView(meta, record = {}, journal = {}) {
  const groups = journal.groups || [];
  const photoSlides = groups.flatMap(group => (group.photos || []).map(photo => ({ group, photo })));
  const textSlides = groups.filter(group => group && group.text);
  return `<div class="workspace"><div class="page-heading"><div><div class="eyebrow"><span></span> A DAY ON TWO WHEELS</div><h1>${record.date ? '再写这一程' : '记录这一程'}</h1><p class="lead">留住沿途风景，也留住此刻的自己。</p></div><span class="date-stamp">${icon('calendar-days')}${displayDate(meta.today)}</span></div>
    <div class="editor-layout"><form id="ride-form" action="/api/generate" method="post" enctype="multipart/form-data">
    <input type="hidden" name="edit_date" value="${e(record.date || '')}">
    <section class="form-section"><div class="section-heading"><span class="section-number">01</span><h2>骑行数据</h2><span class="optional">选填</span></div>
    <div class="metrics-form"><label class="date-field">骑行日期<input type="date" name="date" value="${e(record.date || meta.today)}"></label>
    ${meta.metrics.map(([key, label, unit]) => `<label>${e(label)}<span class="input-unit"><input name="${e(key)}" ${key === 'duration' ? 'type="text" inputmode="text" placeholder="02:30" pattern="[0-9]{1,3}:[0-5][0-9]"' : 'type="number" min="0" max="100000" step="any" placeholder="—"'} value="${e(record[key] ?? '')}"><span>${e(unit)}</span></span></label>`).join('')}</div></section>
    <section class="form-section journey-section"><div class="section-heading"><span class="section-number">02</span><h2>沿途照片</h2><span class="optional">原图展示</span><span id="photo-count" class="section-meta">${photoSlides.length} 张</span></div>
      <div class="journal-carousel photo-carousel" data-carousel>${photoSlides.length ? `<div class="carousel-track">${photoSlides.map(({ group, photo }, index) => `<div class="carousel-slide ${index ? '' : 'is-active'}" data-group-id="${e(group.id)}" data-retained="${e(photo)}"><img src="${photoUrl(photo)}" alt="已保存的骑行照片 ${index + 1}"><button type="button" class="remove-photo" data-group-id="${e(group.id)}" data-photo="${e(photo)}" aria-label="移除照片 ${index + 1}">${icon('x')}</button></div>`).join('')}</div><button type="button" class="carousel-arrow previous" data-carousel-prev aria-label="上一张">${icon('chevron-left')}</button><button type="button" class="carousel-arrow next" data-carousel-next aria-label="下一张">${icon('chevron-right')}</button><span class="carousel-count">1 / ${photoSlides.length}</span>` : `<p class="carousel-empty">还没有照片，上传后会在这里轮播。</p>`}</div>
      <label class="upload-zone" id="drop-zone" for="photo-input"><span class="upload-icon">${icon('image-plus')}</span><strong>上传这一刻的照片</strong><span>JPG、PNG、WebP、苹果照片 · 超过 30 MB 将自动压缩</span><input id="photo-input" class="sr-only" type="file" name="photos" accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif" multiple></label>
      <ul id="pending-photo-names" class="pending-photo-names" aria-live="polite"></ul>
      <p id="photo-error" class="field-error" role="alert" hidden></p></section>
    <section class="form-section journey-section"><div class="section-heading"><span class="section-number">03</span><h2>路上事迹</h2><span class="optional">每次最多 1024 字</span></div>
      <div class="journal-carousel text-carousel" id="text-carousel" data-carousel>${textSlides.length ? `<div class="carousel-track">${textSlides.map((group, index) => `<button type="button" class="carousel-slide text-card ${index ? '' : 'is-active'}" data-group-id="${e(group.id)}" data-text="${e(group.text)}"><span>第 ${index + 1} 次记录</span><p>${e(group.text)}</p><small>点击编辑</small></button>`).join('')}</div><button type="button" class="carousel-arrow previous" data-carousel-prev aria-label="上一条">${icon('chevron-left')}</button><button type="button" class="carousel-arrow next" data-carousel-next aria-label="下一条">${icon('chevron-right')}</button><span class="carousel-count">1 / ${textSlides.length}</span>` : `<p class="carousel-empty">记录路上遇见的人、风景或小插曲。</p>`}</div>
      <label class="journal-input">本次记录<textarea id="journal-text" maxlength="1024" placeholder="这一刻发生了什么？"></textarea><small id="text-length">0 / 1024</small></label>
      <input type="hidden" id="edit-group-id" value=""><div class="edit-actions"><button type="button" class="text-link cancel-edit" id="cancel-text-edit" hidden>取消编辑</button></div>
      <button type="button" class="button secondary journal-save" id="save-journal">${icon('save')}保存本次记录</button><div id="journal-message" class="notice" role="status" hidden></div></section>
    <section class="form-section style-section"><div class="section-heading"><span class="section-number">04</span><h2>给故事一种语气</h2><span class="optional">必选 · 可多选</span></div><div class="style-grid">
      ${meta.styles.map(style => `<label class="style-option ${e(style.id)}"><input type="checkbox" name="styles" value="${e(style.id)}" ${(record.styles || []).includes(style.id) ? 'checked' : ''}><span class="style-icon">${icon(style.icon)}</span><span class="style-copy"><strong>${e(style.label)}</strong><small>${e(style.description)}</small></span></label>`).join('')}</div></section>
    <div class="generation-options"><label class="music-switch"><input type="checkbox" id="background-music" ${journal.background_music ? 'checked' : ''}><span></span><span><strong>添加匹配风格的背景音乐</strong><small>生成时按所选语气配上氛围音乐。</small></span></label></div>
    <div id="form-message" class="notice error" role="alert" hidden></div><div class="submit-row"><span>${icon('sparkles')}<span id="selection-count">选择属于这一程的文案风格</span></span><button type="submit" class="button primary" id="generate-button">${icon('sparkles')}<span>生成骑行故事</span>${icon('arrow-right')}</button></div>
    <div id="generation-status" class="generation-status" role="status" hidden><span class="spinner"></span>正在整理这一程的风景，请稍候…</div></form>
    <aside class="journal-aside"><div class="aside-image"><img src="/assets/cycling.jpg" alt="骑行者行驶在群山之间的公路" loading="lazy"><span>EVERY RIDE, A STORY.</span></div><div class="aside-caption"><span class="eyebrow">你的骑行手记</span><h2>把日子骑成故事。</h2><p>关于远方，也关于每一次<br>平凡而珍贵的出发。</p></div>
      <a class="archive-link" href="/gallery"><span><strong>${e(meta.count)}</strong> 段已珍藏的时光</span>${icon('arrow-up-right')}</a>
      <a class="config-status ${meta.configured ? 'ready' : ''}" href="/settings"><span class="status-dot"></span><span>${meta.configured ? 'AI 已配置' : '生成前，请先配置 AI'}</span>${icon('arrow-right')}</a></aside></div></div>`;
}

export function settingsView(config) {
  return `<div class="settings-layout"><div class="page-heading"><div><div class="eyebrow"><span></span> THE WORDS BEHIND THE RIDE</div><h1>AI 配置</h1><p class="lead">连接你的创作搭档。</p></div><span class="heading-icon">${icon('sliders-horizontal')}</span></div>
    <form id="settings-form" action="/api/config" method="post"><div class="settings-status"><span class="status-dot ${config.has_key ? 'connected' : ''}"></span>${config.has_key ? '配置已保存' : '尚未配置'}</div>
    <label>Base URL <span class="required">必填</span><input type="url" name="base_url" value="${e(config.base_url)}" placeholder="https://api.example.com/v1" required autocomplete="url"></label>
    <label>API Key <span class="required">${config.has_key ? '已保存' : '必填'}</span><span class="password-field"><input type="password" id="api-key" ${config.has_key ? `value="${e(config.api_key_masked)}" readonly data-masked="true" data-masked-value="${e(config.api_key_masked)}" aria-label="已保存的 API Key（已脱敏）"` : 'name="api_key" required placeholder="sk-…"'} autocomplete="new-password"><button class="icon-button password-toggle" type="button" data-target="api-key" aria-label="${config.has_key ? '更换密钥' : '显示密钥'}" title="${config.has_key ? '更换密钥' : '显示密钥'}">${icon(config.has_key ? 'pencil' : 'eye')}</button></span>${config.has_key ? '<small class="field-hint">已保存：留空直接保存会继续使用当前密钥</small>' : ''}</label>
    <label>模型名称 <span class="required">选填</span><input name="model" placeholder="gpt-4o" value="${e(config.model)}"></label>
    <p class="settings-note">${icon('image')}上传照片时，请使用支持图片输入的模型。</p><div id="settings-message" class="notice" role="status" hidden></div>
    <div class="settings-actions"><a class="text-link" href="/">${icon('arrow-left')}返回记录</a><button type="submit" class="button primary">${icon('save')}保存配置</button></div></form></div>`;
}

export function storySchemesView(schemes = {}) {
  const styles = [['funny', '趣味搞笑'], ['inspiring', '热血励志'], ['poetic', '文艺安静'], ['suspense', '恐怖悬疑'], ['cinematic', '电影旁白'], ['diary', '日记随笔']];
  return `<div class="settings-layout story-schemes-layout"><div class="page-heading"><div><div class="eyebrow"><span></span> STORY BLUEPRINTS</div><h1>故事方案配置</h1><p class="lead">为每种故事语气建立你的写作参考。</p></div><span class="heading-icon">${icon('book-open')}</span></div>
    <form id="story-schemes-form" action="/api/story-schemes" method="post"><p class="settings-note">${icon('sparkles')}每次新增一条方案。生成故事时，系统会按所选语气从对应方案中随机选取一条作为参考。</p><label>故事语气<select id="story-scheme-style" name="style">${styles.map(([id, label]) => `<option value="${e(id)}">${e(label)}</option>`).join('')}</select></label><label>参考方案<textarea name="scheme_text" rows="5" maxlength="5000" required placeholder="例如：第一人称，先写路况再写心情，结尾留一个轻松的转折。"></textarea></label><button type="submit" class="button secondary">${icon('plus')}添加方案</button><div id="story-schemes-message" class="notice" role="status" hidden></div>
    <section class="saved-schemes"><h2>已添加方案</h2>${styles.map(([id, label]) => `<div class="scheme-list" data-scheme-list="${e(id)}" ${id === 'funny' ? '' : 'hidden'}>${(schemes[id] || []).length ? (schemes[id] || []).map((scheme, index) => `<article class="scheme-card"><div class="scheme-card-head"><span>${e(label)} · 最新第 ${index + 1} 条</span><button type="button" class="delete-scheme" data-scheme-id="${e(scheme.id)}" aria-label="删除这条方案" title="删除方案">${icon('trash-2')}删除</button></div><p>${e(scheme.text)}</p><time datetime="${e(scheme.created_at)}">${e(new Date(scheme.created_at).toLocaleString('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }))}</time></article>`).join('') : `<p class="scheme-empty">这个语气还没有方案。</p>`}</div>`).join('')}</section>
    <div class="settings-actions"><a class="text-link" href="/settings">${icon('arrow-left')}AI 配置</a></div></form></div>`;
}

export function galleryView(meta, items) {
  const label = id => meta.styles.find(style => style.id === id)?.label || id;
  return `<div class="workspace gallery-workspace"><div class="page-heading"><div><div class="eyebrow"><span></span> MILES INTO MEMORIES</div><h1>时光画廊<span class="heading-count">${items.length}</span></h1><p class="lead">走过的路，都在这里。</p></div><a class="button primary" href="/">${icon('plus')}记录新骑行</a></div>
    ${items.length ? `<div class="gallery-meta"><span>${items.length} 段骑行时光</span><span>${icon('arrow-down-wide-narrow')}最新在前</span></div><div class="gallery-grid">${items.map(item => `<a class="gallery-item" href="/cycling/${encodeURIComponent(item.filename)}"><div class="gallery-cover">${/^\/tmp\/thumbs\/[a-f0-9]{32}\.(?:jpg|jpeg|png|webp)\.jpg$/.test(item.thumbnail || '') ? `<img src="${e(item.thumbnail)}" alt="${e(item.date)} 的骑行照片" loading="lazy">` : `<div class="no-photo">${icon('bike')}<span>CYCLING JOURNAL</span></div>`}<span class="gallery-open">${icon('arrow-up-right')}</span></div><div class="gallery-details"><time datetime="${e(item.date)}">${displayDate(item.date)}</time><h2>${e(item.title)}</h2>${item.summary ? `<p>${e(item.summary)}</p>` : ''}<div class="gallery-tags">${item.distance != null && item.distance !== '' ? `<span>${e(item.distance)} km</span>` : ''}${item.styles.map(style => `<span>${e(label(style))}</span>`).join('')}</div></div></a>`).join('')}</div>` : `<section class="gallery-empty"><span class="empty-icon">${icon('route')}</span><h2>第一段时光，等你出发</h2><p>还没有骑行记录。</p><a href="/" class="button primary">${icon('plus')}记录第一程</a></section>`}</div>`;
}

export function resultView(meta, record) {
  const label = id => meta.styles.find(style => style.id === id)?.label || id;
  const filename = record.filename || record.date.replaceAll('-', '') + '.html';
  const filled = meta.metrics.filter(([key]) => record[key] != null && record[key] !== '');
  const segments = record.story_segments || [];
  return `<div class="preview-layout"><div class="preview-toolbar"><div class="saved-status">${icon('circle-check')}<span>已珍藏这一程<small>${e(filename)}</small></span></div><a href="/gallery" class="text-link">时光画廊${icon('arrow-up-right')}</a></div>
    <article class="ride-story"><div class="story-date"><span>骑行手记</span><time datetime="${e(record.date)}">${displayDate(record.date)}</time></div><h1>${e(record.title)}</h1>
    <div class="story-tags">${record.styles.map(style => `<span>${e(label(style))}</span>`).join('')}</div>
    ${record.photos.length && !segments.length ? `<div class="story-photos">${record.photos.map((photo, index) => `<a href="${photoUrl(photo)}" target="_blank" rel="noopener"><img src="${photoUrl(photo)}" alt="${e(record.date)} 的骑行照片 ${index + 1}" ${index ? 'loading="lazy"' : ''}></a>`).join('')}</div>` : ''}
    ${filled.length ? `<div class="story-metrics">${filled.map(([key, name, unit]) => `<div><span>${e(name)}</span><strong>${e(record[key])} <small>${key === 'duration' ? '' : e(unit)}</small></strong></div>`).join('')}</div>` : ''}
    ${segments.length ? `<div class="story-segments">${segments.map((segment, index) => `<section class="story-segment${segment.photo ? '' : ' story-segment--text-only'}"><div class="story-segment__media">${segment.photo ? `<a href="${photoUrl(segment.photo)}" target="_blank" rel="noopener" aria-label="查看缩略图"><img src="${photoUrl(segment.photo)}" alt="${e(record.date)} 的骑行照片" ${index ? 'loading="lazy"' : ''}></a>` : `<span class="story-segment__placeholder" aria-hidden="true">✻</span>`}</div><div class="story-segment__body"><p class="story-segment__caption">${e(segment.text)}</p></div></section>`).join('')}</div>` : ''}
    <div class="story-entries">${record.entries.map((entry, index) => `<section class="story-entry"><h2><span>${String(index + 1).padStart(2, '0')}</span>${e(label(entry.style))}</h2><p>${e(entry.text)}</p></section>`).join('')}</div>
    <div class="story-signoff"><span></span>这一程，已成为时光<span></span></div></article>
    <div class="preview-actions"><a class="button secondary" href="/?edit=${encodeURIComponent(record.date)}">${icon('pencil')}返回修改</a><a class="button primary" href="/cycling/${encodeURIComponent(filename)}" target="_blank" rel="noopener">${icon('external-link')}查看 HTML</a></div></div>`;
}

export function errorView(message) {
  return `<div class="error-page">${icon('circle-alert')}<h1>暂时没能完成</h1><p role="alert">${e(message)}</p><a href="/" class="button primary">${icon('arrow-left')}回到首页</a></div>`;
}
