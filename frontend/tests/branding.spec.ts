import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

const draft = {
  display_name: 'Àjọ Events', logo_url: null, primary_color: '#46806A', accent_color: '#46806A',
  action_text_color: '#FFFFFF', sender_name: 'Àjọ Events', revision: 2, published_version: null,
};

test('branding editor previews both themes, reflows and confirms publication', async ({ page }) => {
  test.setTimeout(180_000);
  let published = false;
  await page.route('**/api/v1/branding/draft', (route) => route.fulfill({
    json: { ...draft, published_version: published ? 1 : null },
  }));
  await page.route('**/api/v1/branding/history', (route) => route.fulfill({ json: {
    versions: published ? [{ version: 1, display_name: 'Àjọ Events', published_at: '2026-10-24T10:00:00Z',
      restored_from_version: null, has_logo: false }] : [],
    audit: published ? [{ action: 'branding.published', version: 1,
      actor_user_id: '0d33357d-bb71-4f68-95dd-a7d555440c18', occurred_at: '2026-10-24T10:00:00Z' }] : [],
  } }));
  await page.route('**/api/v1/auth/csrf', (route) => route.fulfill({ json: { csrf_token: 'fixture' } }));
  await page.route('**/api/v1/branding/publish', (route) => {
    expect(route.request().headers()['x-csrf-token']).toBe('fixture');
    expect(route.request().postDataJSON()).toEqual({ revision: 2 });
    published = true;
    return route.fulfill({ json: { ...draft, published_version: 1 } });
  });
  await page.goto('/branding.html');
  await expect(page.getByRole('heading', { name: 'Tenant branding' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Light' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Dark' })).toBeVisible();
  await page.getByRole('button', { name: 'Publish branding' }).click();
  await expect(page.getByRole('dialog', { name: 'Publish branding?' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Publish branding' })).toBeFocused();
  await page.getByRole('button', { name: 'Publish branding' }).click();
  await page.getByRole('button', { name: 'Confirm publish' }).click();
  await expect(page.getByText('Version 1', { exact: true })).toBeVisible();
  for (const theme of ['light', 'dark']) {
    await page.getByRole('button', { name: `Use ${theme} theme` }).click();
    await page.setViewportSize({ width: 320, height: 740 });
    await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag22aa']).analyze();
    expect(results.violations).toEqual([]);
  }
});

test('branding validation errors are announced without publishing', async ({ page }) => {
  await page.route('**/api/v1/branding/draft', (route) => {
    if (route.request().method() === 'GET') return route.fulfill({ json: draft });
    return route.fulfill({ status: 422, json: { detail: { code: 'BRANDING_INVALID',
      message: 'Primary color: choose a color visible against both light and dark surfaces (3:1).' } } });
  });
  await page.route('**/api/v1/branding/history', (route) => route.fulfill({ json: { versions: [], audit: [] } }));
  await page.route('**/api/v1/auth/csrf', (route) => route.fulfill({ json: { csrf_token: 'fixture' } }));
  await page.goto('/branding.html');
  await page.getByRole('textbox', { name: 'Primary color' }).fill('#FFFFFF');
  await page.getByRole('button', { name: 'Save draft' }).click();
  await expect(page.getByRole('alert')).toContainText('Primary color');
  await expect(page.getByRole('button', { name: 'Publish branding' })).toBeDisabled();
});
