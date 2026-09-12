const assert = require('node:assert/strict');
const { test } = require('node:test');
const { spawn } = require('node:child_process');
const { mkdtemp } = require('node:fs/promises');
const { join } = require('node:path');
const { chromium } = require('playwright');

test('真实本地后端的注册、登录、个人画廊与root全部画廊', async t => {
  const root = join(__dirname, '..');
  const directory = await mkdtemp(join(root, 'test-results/accounts-'));
  const server = spawn(join(root, '.venv/bin/python'), [join(__dirname, 'accounts_browser_server.py'), directory], { cwd: root });
  let stderr = '';
  server.stderr.on('data', chunk => { stderr += chunk; });
  t.after(() => server.kill());
  const port = await new Promise((resolve, reject) => {
    server.stdout.once('data', chunk => resolve(Number(chunk.toString().trim())));
    server.once('error', reject);
    server.once('exit', code => reject(new Error(`测试后端退出 ${code}: ${stderr}`)));
  });
  const origin = `http://127.0.0.1:${port}`;
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  t.after(() => browser.close());
  const context = await browser.newContext();
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));

  async function createStory() {
    const session = await (await context.request.get(origin + '/api/session')).json();
    const headers = { 'X-CSRF-Token': session.csrf_token };
    assert.equal((await context.request.post(origin + '/api/config', { headers, data: { base_url: 'https://ai.example/v1', api_key: 'browser-test-only' } })).status(), 200);
    const result = await context.request.post(origin + '/api/generate', { headers, data: { date: '2026-09-13', styles: ['poetic'] } });
    assert.equal(result.status(), 200);
    return (await result.json()).record.filename;
  }

  const filenames = [];
  for (const username of ['browser_one', 'browser_two']) {
    await page.goto(origin + '/login');
    await page.getByRole('link', { name: '还没有账号？立即注册' }).click();
    await page.getByLabel('账号', { exact: true }).fill(username);
    await page.getByLabel('密码', { exact: true }).fill('browser-password');
    await page.getByLabel('确认密码', { exact: true }).fill('wrong-password');
    await page.getByRole('button', { name: '注册并登录' }).click();
    await page.getByText('两次输入的密码不一致。', { exact: true }).waitFor();
    await page.getByLabel('确认密码', { exact: true }).fill('browser-password');
    await page.getByRole('button', { name: '注册并登录' }).click();
    await page.waitForURL(origin + '/');
    await page.locator('.account-name').waitFor();
    assert.equal(await page.locator('.account-name').innerText(), username);
    await page.goto(origin + '/gallery');
    await page.locator('.gallery-empty').waitFor();
    filenames.push(await createStory());
    await page.reload();
    await page.locator('.gallery-item').first().waitFor();
    assert.equal(await page.locator('.gallery-item').count(), 1);
    await page.getByRole('button', { name: '退出登录' }).click();
    await page.waitForURL(origin + '/login');
  }
  assert.notEqual(filenames[0], filenames[1]);
  for (const [username, password, count] of [['browser_one', 'browser-password', 1], ['root', 'browser-root-test', 2]]) {
    await page.getByLabel('账号', { exact: true }).fill(username);
    await page.getByLabel('密码', { exact: true }).fill(password);
    await page.getByRole('button', { name: '登录', exact: true }).click();
    await page.waitForURL(origin + '/');
    await page.goto(origin + '/gallery');
    await page.locator('.gallery-item').first().waitFor();
    assert.equal(await page.locator('.gallery-item').count(), count);
    await page.getByRole('button', { name: '退出登录' }).click();
    await page.waitForURL(origin + '/login');
  }
  assert.deepEqual(errors, []);
});
