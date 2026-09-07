let csrfToken = '';

export async function request(path, { method = 'GET', body } = {}) {
  const headers = { Accept: 'application/json' };
  if (method !== 'GET') headers['X-CSRF-Token'] = csrfToken;
  if (body && !(body instanceof FormData)) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(path, { method, body, headers, credentials: 'same-origin' });
  } catch {
    throw new Error('网络连接中断，请检查连接后重试。');
  }
  let result;
  try { result = await response.json(); }
  catch { throw new Error('服务暂时不可用，请稍后重试。'); }
  if (response.status === 401 && result.redirect === '/login') {
    window.location.replace('/login');
  }
  if (!response.ok) throw new Error(result.error || '请求未完成，请重试。');
  if (result.csrf_token) csrfToken = result.csrf_token;
  return result;
}

export const postForm = (url, data) => request(url, { method: 'POST', body: data });
