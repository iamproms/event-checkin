import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

const domain = {
  id: '6d36b5da-ccca-4a87-b858-b868620536f5',
  hostname: 'xn--bcher-kva.example.test',
  kind: 'custom', ownership: 'verified', tls: 'active', routing: 'ready',
  primary: false, serving: false, error_code: null,
};

async function checkLayouts(page: Page) {
  for (const theme of ['light', 'dark'] as const) {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.getByRole('button', { name: `Use ${theme} theme` }).click();
    await page.setViewportSize({ width: 320, height: 740 });
    await expect(page.getByRole('group', { name: 'Theme preference' })).toBeVisible();
    await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
    await expect(page.getByRole('group', { name: 'Theme preference' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag22aa']).analyze();
    expect(results.violations).toEqual([]);
  }
}

test('tenant domain page uses actionable state text, keyboard controls and both themes', async ({ page }) => {
  test.setTimeout(120_000);
  await page.route('**/api/v1/domains', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ json: { domains: [domain] } });
    } else {
      await route.fulfill({ status: 201, json: { domain_id: domain.id,
        dns_record: '_eventcheckin-verify.example.test', dns_value: 'proof' } });
    }
  });
  await page.route('**/api/v1/auth/csrf', (route) => route.fulfill({ json: { csrf_token: 'fixture' } }));
  await page.goto('/domains.html');
  await expect(page.getByText('Awaiting activation')).toBeVisible();
  await expect(page.getByText('A platform administrator must approve activation.')).toBeVisible();
  await page.getByRole('textbox', { name: 'Custom hostname' }).fill('events.example.test');
  await page.getByRole('button', { name: 'Request claim' }).click();
  await expect(page.getByText('DNS TXT value: proof')).toBeVisible();
  await checkLayouts(page);
});

test('platform page keeps MFA required and exposes review actions after an authorized session', async ({ page }) => {
  await page.route('**/api/v1/platform/auth/session', (route) =>
    route.fulfill({ json: { user_id: 'actor', email: 'operator@example.test', permission: 'tenant.provision' } }));
  await page.route('**/api/v1/platform/tenants/*/domains', (route) =>
    route.fulfill({ json: { domains: [domain] } }));
  await page.goto('/platform.html');
  await page.getByRole('link', { name: 'Organizations' }).click();
  await page.getByRole('textbox', { name: 'Tenant ID' }).fill('c1526557-cdf0-49b8-89a0-3516ab47ab41');
  await page.getByRole('button', { name: 'Load domains' }).click();
  await expect(page.getByText('Awaiting activation')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Approve activation' })).toBeVisible();
  await checkLayouts(page);
});

test('platform sign-in does not expose provisioning before MFA', async ({ page }) => {
  await page.route('**/api/v1/platform/auth/session', (route) =>
    route.fulfill({ status: 401, json: { detail: { code: 'AUTH_DENIED', message: 'Authentication required' } } }));
  await page.route('**/api/v1/platform/auth/csrf', (route) => route.fulfill({ json: { csrf_token: 'fixture' } }));
  await page.route('**/api/v1/platform/auth/login', (route) =>
    route.fulfill({ json: { state: 'mfa' } }));
  await page.goto('/platform.html');
  await page.getByRole('textbox', { name: 'Verified staff email' }).fill('operator@example.test');
  await page.getByLabel('Password', { exact: true }).fill('fixture-password');
  await page.getByRole('button', { name: 'Continue' }).click();
  await expect(page.getByRole('heading', { name: 'Verify your identity' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Reserve organization' })).toHaveCount(0);
});

test('owner invitation reissue requires confirmation and clears stale data on revocation', async ({ page }) => {
  let reissues = 0;
  await page.route('**/api/v1/platform/auth/session', (route) =>
    route.fulfill({ json: { user_id: 'actor', email: 'operator@example.test', permission: 'tenant.provision' } }));
  await page.route('**/api/v1/platform/auth/csrf', (route) =>
    route.fulfill({ json: { csrf_token: 'fixture' } }));
  await page.route('**/api/v1/platform/tenants/*/owner-invitations/reissue', (route) => {
    reissues += 1;
    return route.fulfill({ status: 403,
      json: { detail: { code: 'AUTH_DENIED', message: 'Authentication required' } } });
  });
  await page.goto('/platform.html');
  await page.getByRole('link', { name: 'Organizations' }).click();
  await page.getByRole('textbox', { name: 'Tenant ID' }).fill('c1526557-cdf0-49b8-89a0-3516ab47ab41');
  await page.getByRole('button', { name: 'Reissue pending invitation' }).click();
  await expect(page.getByRole('dialog', { name: 'Reissue owner invitation' })).toBeVisible();
  await expect(page.getByRole('dialog').getByText('The current invitation will stop working.')).toBeVisible();
  await page.getByRole('button', { name: 'Cancel' }).click();
  expect(reissues).toBe(0);
  await page.getByRole('button', { name: 'Reissue pending invitation' }).click();
  await page.getByRole('button', { name: 'Revoke and reissue' }).click();
  await expect(page.getByRole('button', { name: 'Reserve organization' })).toHaveCount(0);
  await expect(page.getByText('Your platform session is unavailable. Sign in again.')).toBeVisible();
  expect(reissues).toBe(1);
});
