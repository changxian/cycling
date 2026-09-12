const assert = require('node:assert/strict');
const { test } = require('node:test');
const { createServer } = require('node:http');
const { readFile } = require('node:fs/promises');
const { join } = require('node:path');
const { chromium } = require('playwright');

const journal = {
  date: '2026-09-12', background_music: false,
  groups: [
    { id: '8372e30ca705379e2c177745', photos: ['016ebab4a46bda4da0bb7c0f42939ad5.jpg'], text: '停一脚拍个照再走' },
    { id: 'bf01d47f58cb7c9ea3c2fe80', photos: ['1f5c53aa50f50a8365751c610884a16a.jpg'], text: '停一停风景最重要' },
    { id: 'f6a36bba846edc0b82f5cb07', photos: ['f2d8886a351ab5008c15aab6bf8f2da2.jpg'], text: '' },
    { id: '4a6f2f0d3105b9fe02545a27', photos: ['5575b1fdd1808d76cadd261930295839.jpg'], text: '' },
    { id: 'c98c957663ccefd6ef9542a9', photos: ['8d75069fe8e36aac3a233f6991883074.png'], text: '' },
  ],
};

test('旧缓存兼容及待上传图片的轮播预览、叠加、移除与保存', async t => {
  let seedCache = true;
  let servedJournal = journal;
  const record = {
    date: journal.date, filename: '20260912_2.html', title: '第二程',
    photos: [], entries: [{ style: 'poetic', text: '第二程故事' }], styles: ['poetic'],
  };
  const scriptRequests = [];
  let submittedBody = '';
  const server = createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost');
    try {
      if (url.pathname === '/seed') {
        res.setHeader('Content-Type', 'text/html');
        return res.end('<script type="module">import "/src/views.js"; window.cacheReady = true;</script>');
      }
      if (url.pathname.startsWith('/api/')) {
        if (req.method === 'POST' && url.pathname === '/api/journals') {
          const chunks = [];
          for await (const chunk of req) chunks.push(chunk);
          submittedBody = Buffer.concat(chunks).toString();
        }
        const result = url.pathname === '/api/session' ? { authenticated: true, csrf_token: 'test-session' }
          : url.pathname === '/api/meta' ? { today: journal.date, metrics: [], styles: [] }
          : url.pathname === '/api/result' ? { record }
          : { journal: servedJournal };
        res.setHeader('Content-Type', 'application/json');
        res.setHeader('Cache-Control', 'no-store');
        return res.end(JSON.stringify(result));
      }
      if (url.pathname.startsWith('/tmp/')) {
        res.setHeader('Content-Type', 'image/png');
        return res.end(Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64'));
      }
      const file = ['/', '/generate'].includes(url.pathname) ? '/index.html' : url.pathname;
      let content = await readFile(join(__dirname, '../frontend', file));
      res.setHeader('Content-Type', file.endsWith('.js') ? 'application/javascript' : file.endsWith('.css') ? 'text/css' : 'text/html');
      res.setHeader('Cache-Control', file.endsWith('.js') ? 'public, max-age=31536000' : 'no-store');
      if (file.endsWith('.js')) scriptRequests.push(req.url);
      if (seedCache && file === '/src/views.js') {
        // 浏览器实际旧代码读取 photos/texts；模拟同一 URL 曾缓存过这套数据模型。
        content = content.toString().replace('const groups = journal.groups || [];', `
          const savedPhotos = journal.photos || record.photos || [];
          const savedTexts = journal.texts || [];
          const groups = [...savedTexts.map(entry => ({ ...entry, photos: [] })), { id: 'legacy', text: '', photos: savedPhotos }];
        `);
      }
      res.end(content);
    } catch { res.writeHead(404).end(); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  t.after(() => browser.close());
  const page = await browser.newPage({ reducedMotion: 'reduce' });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const origin = `http://127.0.0.1:${server.address().port}`;
  await page.goto(origin + '/seed');
  await page.waitForFunction(() => window.cacheReady);
  seedCache = false;
  await page.goto(origin + '/');
  await page.locator('#main-content[aria-busy="false"]').waitFor();
  assert.equal(await page.locator('.photo-carousel .carousel-slide').count(), 5);
  assert.equal(await page.locator('#text-carousel .text-card').count(), 2);
  assert.equal(await page.locator('#text-carousel .is-active p').innerText(), journal.groups[0].text);
  await page.locator('#text-carousel [data-carousel-next]').click();
  assert.equal(await page.locator('#text-carousel .is-active p').innerText(), journal.groups[1].text);
  await page.waitForFunction(() => [...document.querySelectorAll('.photo-carousel img')].every(img => img.complete && img.naturalWidth > 0));
  assert.equal(scriptRequests.filter(url => url === '/src/views.js').length, 1);
  assert.ok(scriptRequests.some(url => url.startsWith('/src/views.js?v=')));
  const localPhoto = {
    name: 'local.png', mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64'),
  };
  await page.locator('#photo-input').setInputFiles(localPhoto);
  assert.equal(await page.locator('#photo-count').innerText(), '6 张');
  await page.locator('.photo-carousel [data-carousel-next]').click();
  page.once('dialog', dialog => dialog.accept());
  await page.locator('.photo-carousel .is-active .remove-photo').click();
  await page.waitForFunction(() => document.querySelectorAll('.photo-carousel .carousel-slide').length === 5);
  assert.equal(await page.locator('#pending-photo-names li').count(), 1);
  assert.equal(await page.locator('#text-carousel .text-card').count(), 1);
  assert.equal(await page.locator('#photo-count').innerText(), '5 张');
  servedJournal = { ...journal, groups: [] };
  await page.reload();
  await page.locator('#main-content[aria-busy="false"]').waitFor();
  assert.equal(await page.locator('.photo-carousel .carousel-slide').count(), 0);
  assert.equal(await page.locator('#text-carousel .text-card').count(), 0);
  assert.equal(await page.locator('.photo-carousel .carousel-empty').count(), 1);
  // 连续两次选择必须累加；保存请求也必须携带全部文件。
  const photos = Array.from({ length: 6 }, (_, index) => ({
    name: `photo-${index + 1}.png`, mimeType: 'image/png',
    buffer: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64'),
  }));
  await page.locator('#photo-input').setInputFiles(photos.slice(0, 5));
  assert.equal(await page.locator('#pending-photo-names li').count(), 5);
  assert.equal(await page.locator('.photo-carousel .carousel-slide').count(), 5);
  await page.waitForFunction(() => [...document.querySelectorAll('.photo-carousel img')].every(img => img.complete && img.naturalWidth > 0));
  await page.locator('#photo-input').setInputFiles(photos.slice(5));
  assert.deepEqual(await page.locator('#pending-photo-names li span').allTextContents(), photos.map(photo => photo.name));
  assert.equal(await page.locator('#photo-count').innerText(), '6 张');
  assert.equal(await page.locator('.photo-carousel .carousel-slide').count(), 6);
  assert.equal(await page.locator('.photo-carousel .carousel-count').innerText(), '6 / 6');
  await page.locator('.photo-carousel [data-carousel-prev]').click();
  assert.equal(await page.locator('.photo-carousel .carousel-count').innerText(), '5 / 6');
  await page.locator('.photo-carousel [data-carousel-next]').click();
  // 取消选择与误选不支持的文件，都不能覆盖已经选好的图片。
  await page.locator('#photo-input').setInputFiles([]);
  await page.locator('#photo-input').setInputFiles({ name: 'invalid.txt', mimeType: 'text/plain', buffer: Buffer.from('无效') });
  assert.equal(await page.locator('#pending-photo-names li').count(), 6);
  await page.locator('.photo-carousel .is-active .remove-pending-photo').click();
  assert.equal(await page.locator('#pending-photo-names li').count(), 5);
  await page.locator('#pending-photo-names .remove-pending-photo').first().click();
  assert.equal(await page.locator('.photo-carousel .carousel-slide').count(), 4);
  assert.equal(await page.locator('#photo-count').innerText(), '4 张');
  const savedRequest = page.waitForResponse(response => response.request().method() === 'POST' && response.url().endsWith('/api/journals'));
  const savedNavigation = page.waitForEvent('framenavigated', frame => frame === page.mainFrame());
  await page.locator('#save-journal').click();
  await savedRequest;
  assert.deepEqual([...submittedBody.matchAll(/filename="([^"]+)"/g)].map(match => match[1]), photos.slice(1, 5).map(photo => photo.name));
  await savedNavigation;
  await page.locator('#main-content[aria-busy="false"]').waitFor();
  await page.locator('#photo-input').setInputFiles(localPhoto);
  await page.locator('.photo-carousel .is-active .remove-pending-photo').click();
  assert.equal(await page.locator('#pending-photo-names li').count(), 0);
  assert.equal(await page.locator('#photo-count').innerText(), '0 张');
  assert.equal(await page.locator('.photo-carousel .carousel-empty').isVisible(), true);
  await page.locator('#photo-input').setInputFiles(localPhoto);
  assert.equal(await page.locator('.photo-carousel .carousel-slide.is-active').count(), 1);
  assert.equal(await page.locator('.photo-carousel .carousel-count').innerText(), '1 / 1');
  await page.locator('#drop-zone').evaluate((drop, bytes) => {
    const transfer = new DataTransfer();
    transfer.items.add(new File([new Uint8Array(bytes)], 'dropped.png', { type: 'image/png' }));
    drop.dispatchEvent(new DragEvent('drop', { bubbles: true, dataTransfer: transfer }));
  }, [...localPhoto.buffer]);
  assert.equal(await page.locator('.photo-carousel .carousel-slide').count(), 2);
  assert.equal(await page.locator('#photo-count').innerText(), '2 张');
  await page.locator('#photo-input').setInputFiles({ name: 'unsupported.heic', mimeType: 'image/heic', buffer: Buffer.from('无法解码的照片') });
  await page.waitForFunction(() => document.querySelector('.photo-carousel .is-active .pending-photo-label').textContent.includes('浏览器无法预览'));
  assert.equal(await page.locator('.photo-carousel .is-active .remove-pending-photo').isVisible(), true);
  await page.locator('.photo-carousel .is-active .remove-pending-photo').click();
  assert.equal(await page.locator('#photo-count').innerText(), '2 张');
  await page.goto(origin + '/generate?date=2026-09-12');
  await page.locator('#main-content[aria-busy="false"]').waitFor();
  assert.equal(await page.locator('.saved-status small').innerText(), '20260912_2.html');
  assert.equal(await page.getByRole('link', { name: '查看 HTML' }).getAttribute('href'), '/cycling/20260912_2.html');
  assert.deepEqual(errors, []);
});
