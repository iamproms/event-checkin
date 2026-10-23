import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const css = readFileSync(new URL('../src/ui/tokens.css', import.meta.url), 'utf8');
const block = (selector) => css.split(`${selector} {`, 2)[1]?.split('\n}', 1)[0] ?? '';
const tokens = (source) => Object.fromEntries([...source.matchAll(/(--[a-z-]+):\s*(#[0-9a-fA-F]{6});/g)].map(([, key, value]) => [key, value]));
const light = tokens(block(':root'));
const dark = { ...light, ...tokens(block(":root[data-theme='dark']")) };

function luminance(hex) {
  const rgb = [1, 3, 5].map((index) => parseInt(hex.slice(index, index + 2), 16) / 255);
  const linear = rgb.map((value) => value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4);
  return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
}

function contrast(a, b) {
  const x = luminance(a), y = luminance(b);
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

test('selected light and dark foundation pairs meet text and meaningful boundary contrast', () => {
  for (const [name, theme] of Object.entries({ light, dark })) {
    for (const [foreground, background] of [
      ['--text', '--canvas'], ['--text-muted', '--surface'], ['--action-text', '--action'],
      ['--action-text', '--action-hover'], ['--danger-action-text', '--danger-action'],
      ['--status-success-text', '--status-success-bg'], ['--status-warning-text', '--status-warning-bg'],
      ['--status-danger-text', '--status-danger-bg'], ['--status-info-text', '--status-info-bg'],
    ]) assert.ok(contrast(theme[foreground], theme[background]) >= 4.5, `${name} ${foreground}/${background}`);
    for (const [foreground, background] of [
      ['--border-control', '--surface'], ['--focus', '--canvas'], ['--focus', '--surface'],
    ]) assert.ok(contrast(theme[foreground], theme[background]) >= 3, `${name} ${foreground}/${background}`);
  }
});

test('semantic and focus tokens are not tenant brand aliases', () => {
  assert.doesNotMatch(css, /var\(--tenant-[^)]+\)/);
  assert.doesNotMatch(css, /prefers-color-scheme/);
  assert.match(css, /\[data-theme='dark'\]/);
  assert.match(css, /\[data-density='compact'\]/);
});
