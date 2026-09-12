import assert from 'node:assert/strict';
import test from 'node:test';

import { collectPhotoFiles } from '../frontend/src/photo-files.js';

test('重新选择图片会替换上一次失败遗留的待上传文件', () => {
  const unsupported = { name: 'unknown-image.bin', type: 'image/heif' };
  const png = { name: 'Screenshot.PNG', type: 'image/png' };

  const result = collectPhotoFiles([unsupported], [png], { replace: true });

  assert.deepEqual(result.files, [png]);
  assert.equal(result.error, null);
});

test('拖放有效图片会追加到待上传列表', () => {
  const first = { name: 'first.png', type: 'image/png' };
  const second = { name: 'second.PNG', type: '' };

  const result = collectPhotoFiles([first], [second]);

  assert.deepEqual(result.files, [first, second]);
  assert.equal(result.error, null);
});
