import assert from 'node:assert/strict';
import test from 'node:test';
import { editorView, galleryView, resultView } from '../frontend/src/views.js';

test('记录页和故事详情使用内嵌缩略图，故事详情点击打开原图，画廊保留缩略图 URL', () => {
  const name = 'a'.repeat(32) + '.png';
  const thumbnail = `/tmp/thumbs/${name}.jpg`;
  const original = `/tmp/${name}`;
  const preview = 'data:image/jpeg;base64,AAAA';
  const meta = { today: '2026-09-12', metrics: [], styles: [] };
  const record = {
    date: meta.today,
    photos: [name],
    photo_previews: { [name]: preview },
    styles: [],
    entries: [],
    filename: '20260912_2.html',
  };
  const journal = {
    groups: [{ id: 'group', text: '', photos: [name] }],
    photo_previews: { [name]: preview },
  };

  const editor = editorView(meta, {}, journal);
  assert.match(editor, new RegExp(`src="${preview}"`));
  assert.doesNotMatch(editor, new RegExp(`src="${thumbnail}"`));

  const gallery = galleryView(meta, [{ ...record, thumbnail }]);
  assert.match(gallery, new RegExp(`src="${thumbnail}"`));

  for (const html of [resultView(meta, record), resultView(meta, {
    ...record,
    story_segments: [{ photo: name, text: '骑行记录' }],
  })]) {
    assert.match(html, new RegExp(`src="${preview}"`));
    assert.match(html, new RegExp(`href="${original}"`));
    assert.doesNotMatch(html, new RegExp(`href="${thumbnail}"`));
  }
});
