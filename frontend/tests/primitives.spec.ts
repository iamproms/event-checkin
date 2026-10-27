import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

async function openLab(page: Page) {
  await page.goto('/ui-lab.html');
  await page.evaluate(() => document.fonts.ready);
}

test('labels, errors, semantic status and control states are exposed', async ({ page }) => {
  await openLab(page);
  const faces = await page.evaluate(async () => (await document.fonts.load('400 16px Inter', 'Ọláwálé ₦')).map((face) => face.status));
  expect(faces).toContain('loaded');
  await expect(page.getByRole('textbox', { name: 'Coordinator name' })).toHaveValue('Ọláwálé Adébáyọ̀');
  const email = page.getByRole('textbox', { name: 'Contact email' });
  await expect(email).toHaveAttribute('aria-invalid', 'true');
  await expect(email).toHaveAttribute('aria-describedby', /error/);
  await expect(page.getByText('Enter a valid email address to continue.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Unavailable' })).toBeDisabled();
  const loading = page.getByRole('button', { name: 'Saving changes…' });
  await expect(loading).toHaveAttribute('aria-disabled', 'true');
  await expect(loading).toHaveAttribute('aria-busy', 'true');
  await loading.focus();
  await expect(loading).toBeFocused();
  await expect(page.getByRole('alert')).toContainText('Enter a valid email address to continue.');
  await expect(page.getByRole('link', { name: 'Overview' })).toHaveAttribute('aria-current', 'page');
  await expect(page.getByText('Do not admit a second time; seek a supervisor if needed.')).toBeVisible();
  await expect(page.getByRole('progressbar', { name: 'Import preview' })).toHaveAttribute('value', '45');
});

test('theme follows system until an explicit choice is persisted', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await openLab(page);
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByRole('button', { name: 'Use light theme' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.getByRole('button', { name: 'Use system theme' }).click();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
});

test('dialog traps focus, closes on Escape, and restores trigger focus', async ({ page }) => {
  await openLab(page);
  const trigger = page.getByRole('button', { name: 'Open dialog' });
  await trigger.focus();
  await trigger.click();
  const dialog = page.getByRole('dialog', { name: 'Confirm action' });
  await expect(dialog).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(dialog.locator(':focus')).toHaveCount(1);
  await page.keyboard.press('Escape');
  await expect(dialog).not.toBeVisible();
  await expect(trigger).toBeFocused();
});

test('320px reflow, doubled text, and compact touch targets', async ({ page, browserName }) => {
  test.skip(browserName !== 'chromium');
  await page.setViewportSize({ width: 320, height: 740 });
  await openLab(page);
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  const overflow = await page.evaluate(() => ({
    width: document.documentElement.scrollWidth,
    roots: [document.documentElement, document.body].map(node => ({ node: node.tagName.toLowerCase(), scrollWidth: node.scrollWidth, clientWidth: node.clientWidth, width: node.getBoundingClientRect().width })),
    offenders: [...document.querySelectorAll('body *')].map((node) => ({ node: node.tagName.toLowerCase(), className: node.getAttribute('class'), text: node.textContent?.trim().slice(0, 35), scrollWidth: node.scrollWidth, clientWidth: node.clientWidth, left: Math.floor(node.getBoundingClientRect().left), right: Math.ceil(node.getBoundingClientRect().right), width: Math.ceil(node.getBoundingClientRect().width) })).filter((item) => item.right > innerWidth + 1 || item.left < -1 || item.scrollWidth > item.clientWidth + 1).slice(0, 12),
  }));
  expect(overflow.width, JSON.stringify({ roots: overflow.roots, offenders: overflow.offenders })).toBeLessThanOrEqual(320);
  await page.getByRole('button', { name: 'Use compact density' }).click();
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const touch = page.getByRole('button', { name: 'Gate action' });
  const box = await touch.boundingBox();
  expect(box?.height).toBeGreaterThanOrEqual(44);
  expect(box?.width).toBeGreaterThanOrEqual(44);
  await expect(page.getByRole('button', { name: 'Continue', exact: true }).first()).toBeVisible();
});

test('light and dark specimens have no detectable WCAG 2.2 AA violations', async ({ page }) => {
  test.setTimeout(180_000);
  await openLab(page);
  for (const theme of ['light', 'dark'] as const) {
    await page.getByRole('button', { name: `Use ${theme} theme` }).click();
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag22aa']).analyze();
    expect(results.violations).toEqual([]);
  }
});

test('rendered theme pixels and component geometry match approved tokens', async ({ page }, testInfo) => {
  await openLab(page);
  async function sampleCanvas(): Promise<string> {
    const shot = await page.screenshot({ animations: 'disabled' });
    await testInfo.attach(`primitives-${await page.locator('html').getAttribute('data-theme')}.png`, { body: shot, contentType: 'image/png' });
    return page.evaluate(async (base64) => {
      const image = new Image();
      image.src = `data:image/png;base64,${base64}`;
      await image.decode();
      const canvas = document.createElement('canvas');
      canvas.width = image.width; canvas.height = image.height;
      const context = canvas.getContext('2d');
      if (!context) throw new Error('Canvas unavailable');
      context.drawImage(image, 0, 0);
      return Array.from(context.getImageData(1, 1, 1, 1).data).slice(0, 3).map((value) => value.toString(16).padStart(2, '0')).join('');
    }, shot.toString('base64'));
  }
  expect(await sampleCanvas()).toBe('f7f6f3');
  expect((await page.getByRole('button', { name: 'Continue', exact: true }).first().boundingBox())?.height).toBe(44);
  await page.getByRole('button', { name: 'Use dark theme' }).click();
  await page.getByRole('button', { name: 'Use compact density' }).click();
  expect(await sampleCanvas()).toBe('171816');
  const geometry = await page.getByRole('button', { name: 'Continue', exact: true }).first().evaluate((button) => ({
    height: button.getBoundingClientRect().height,
    minHeight: getComputedStyle(button).minHeight,
    lineHeight: getComputedStyle(button).lineHeight,
    padding: getComputedStyle(button).padding,
    density: button.closest('[data-density]')?.getAttribute('data-density'),
    pointerCoarse: matchMedia('(pointer: coarse)').matches,
  }));
  expect(geometry.height, JSON.stringify(geometry)).toBe(geometry.pointerCoarse ? 44 : 38);
});

test('published text, control, focus and status token pairs meet contrast minima', async ({ page }) => {
  await openLab(page);
  for (const theme of ['light', 'dark'] as const) {
    await page.getByRole('button', { name: `Use ${theme} theme` }).click();
    const ratios = await page.evaluate(() => {
      const css = getComputedStyle(document.documentElement);
      const channel = (part: string) => { const n = parseInt(part, 16) / 255; return n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4; };
      const luminance = (token: string) => {
        const hex = css.getPropertyValue(token).trim().slice(1);
        const [r, g, b] = [hex.slice(0, 2), hex.slice(2, 4), hex.slice(4, 6)].map(channel);
        return .2126 * r + .7152 * g + .0722 * b;
      };
      const ratio = (a: string, b: string) => { const x = luminance(a), y = luminance(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
      return {
        text: ratio('--text', '--canvas'), muted: ratio('--text-muted', '--surface'),
        action: ratio('--action-text', '--action'), actionHover: ratio('--action-text', '--action-hover'),
        destructive: ratio('--danger-action-text', '--danger-action'),
        control: ratio('--border-control', '--surface'), focusCanvas: ratio('--focus', '--canvas'), focusSurface: ratio('--focus', '--surface'),
        success: ratio('--status-success-text', '--status-success-bg'),
        warning: ratio('--status-warning-text', '--status-warning-bg'),
        danger: ratio('--status-danger-text', '--status-danger-bg'),
        info: ratio('--status-info-text', '--status-info-bg'),
      };
    });
    for (const name of ['text', 'muted', 'action', 'actionHover', 'destructive', 'success', 'warning', 'danger', 'info'] as const) expect(ratios[name], `${theme} ${name}`).toBeGreaterThanOrEqual(4.5);
    for (const name of ['control', 'focusCanvas', 'focusSurface'] as const) expect(ratios[name], `${theme} ${name}`).toBeGreaterThanOrEqual(3);
  }
});
