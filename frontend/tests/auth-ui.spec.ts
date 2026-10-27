import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

test('migrated login keeps the CSRF and MFA request contract', async ({ page }) => {
  await page.route('**/api/v1/auth/session', (route) => route.fulfill({ status: 401, body: '{}' }));
  await page.route('**/api/v1/auth/csrf', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ csrf_token: 'test-csrf' }) }));
  await page.route('**/api/v1/auth/login', async (route) => {
    expect(route.request().headers()['x-csrf-token']).toBe('test-csrf');
    expect(route.request().postDataJSON()).toEqual({ email: 'staff@example.org', password: 'correct horse battery staple' });
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ state: 'mfa' }) });
  });
  await page.goto('/');
  await page.getByRole('textbox', { name: 'Email address' }).fill('staff@example.org');
  await page.getByLabel('Password').fill('correct horse battery staple');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Verify your identity' })).toBeVisible();
  await expect(page.getByLabel('Six-digit code')).toBeVisible();
});

test('auth failure is announced without removing field labels', async ({ page }) => {
  await page.route('**/api/v1/auth/session', (route) => route.fulfill({ status: 401, body: '{}' }));
  await page.route('**/api/v1/auth/csrf', (route) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ csrf_token: 'test-csrf' }) }));
  await page.route('**/api/v1/auth/login', (route) => route.fulfill({ status: 401, contentType: 'application/json', body: JSON.stringify({ detail: { code: 'invalid_credentials', message: 'Sign-in failed.' } }) }));
  await page.goto('/');
  await page.getByRole('textbox', { name: 'Email address' }).fill('staff@example.org');
  await page.getByLabel('Password').fill('incorrect password');
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page.getByRole('alert')).toContainText('Sign-in failed.');
  await expect(page.getByLabel('Password')).toBeVisible();
});

test('auth form reflows and passes automated accessibility checks in both themes', async ({ page }) => {
  await page.route('**/api/v1/auth/session', (route) => route.fulfill({ status: 401, body: '{}' }));
  await page.setViewportSize({ width: 320, height: 740 });
  await page.goto('/');
  await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
  for (const theme of ['light', 'dark'] as const) {
    await page.getByLabel('Theme preference').selectOption(theme);
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag22aa']).analyze();
    expect(results.violations).toEqual([]);
  }
});
