import assert from 'node:assert/strict';
import test from 'node:test';

import { collectPhotoFiles } from '../frontend/src/photo-files.js';

test('拖放有效图片会追加到待上传列表', () => {
  const first = { name: 'first.png', type: 'image/png' };
  const second = { name: 'second.PNG', type: '' };

  const result = collectPhotoFiles([first], [second]);

  assert.deepEqual(result.files, [first, second]);
  assert.equal(result.error, null);
});

test('再次选择图片会在原有待上传列表上叠加', () => {
  const previous = Array.from({ length: 5 }, (_, index) => ({ name: `photo-${index + 1}.png`, type: 'image/png' }));
  const next = [{ name: 'photo-6.png', type: 'image/png' }];

  const result = collectPhotoFiles(previous, next);

  assert.deepEqual(result.files, [...previous, ...next]);
  assert.equal(result.files.length, 6);
  assert.equal(result.error, null);
});

test('选择中混入不支持格式时保留原列表并报错', () => {
  const previous = [{ name: 'first.png', type: 'image/png' }];
  const next = [{ name: 'invalid.txt', type: 'text/plain' }];

  const result = collectPhotoFiles(previous, next);

  assert.deepEqual(result.files, previous);
  assert.equal(result.error, '请选择 JPG、PNG、WebP 或苹果照片格式。');
});
