import assert from 'node:assert/strict';
import test from 'node:test';
import { editorView, galleryView, resultView } from '../frontend/src/views.js';

test('记录页、画廊和两种故事预览均使用缩略图', () => {
  const name = 'a'.repeat(32) + '.png';
  const thumbnail = `/tmp/thumbs/${name}.jpg`;
  const meta = { today: '2026-09-12', metrics: [], styles: [] };
  const record = { date: meta.today, photos: [name], styles: [], entries: [], filename: '20260912_2.html' };
  const journal = { groups: [{ id: 'group', text: '', photos: [name] }] };
  const pages = [
    editorView(meta, {}, journal),
    galleryView(meta, [{ ...record, thumbnail }]),
    resultView(meta, record),
    resultView(meta, { ...record, story_segments: [{ photo: name, text: '骑行记录' }] }),
  ];
  for (const html of pages) {
    const images = [...html.matchAll(/<img\b[^>]*src="([^"]+)"/g)].filter(match => !match[1].startsWith('/assets/'));
    assert.ok(images.length > 0);
    assert.ok(images.every(match => match[1] === thumbnail));
    assert.ok(!html.includes(`href="/tmp/${name}"`));
    assert.ok(!html.includes(`href="/cycling/photos/${name}"`));
  }
});
