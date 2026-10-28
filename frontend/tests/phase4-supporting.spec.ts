import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

async function mockOrganizer(page: Page) {
  await page.route('**/api/v1/auth/session', route => route.fulfill({ json: {
    email: 'organizer@example.test', role: 'tenant_owner', tenant_id: 'tenant-1',
  } }));
  await page.route('**/api/v1/events', route => route.fulfill({ json: { events: [{
    id: 'event-1', slug: 'summit', name: 'Innovation Summit 2026', status: 'published',
    starts_at: '2026-11-01T08:00:00Z', ends_at: '2026-11-01T18:00:00Z', revision: 1,
  }] } }));
  await page.route('**/api/v1/events/event-1/attendance', route => route.fulfill({ json: {
    event_id: 'event-1', registered: 20, checked_in: 12, remaining: 8,
    attendance_percent: 60, duplicate_scans: 1, invalid_scans: 2,
    refreshed_at: '2026-11-01T09:10:00Z', gates: [], recent: [],
  } }));
}

test('platform console distinguishes connected provisioning from unavailable directories and privacy controls', async ({ page }) => {
  await page.route('**/api/v1/platform/auth/session', route => route.fulfill({ status: 401, json: {} }));
  await page.goto('/platform-console.html#organizations');
  await expect(page.getByRole('heading', { name: 'Platform administrator access required' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Organization directory is unavailable' })).toBeVisible();
  await page.getByRole('link', { name: 'Privacy' }).click();
  await expect(page.getByRole('heading', { name: 'Privacy notices', level: 1 })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Privacy notice management is unavailable' })).toBeVisible();
  await expect(page.getByText('No policy state is inferred in this console.')).toBeVisible();
});

test('incomplete invitation and reset links never submit credentials', async ({ page }) => {
  await page.goto('/reset');
  await expect(page.getByRole('heading', { name: 'Choose a new password' })).toBeVisible();
  await expect(page.getByText('This link is incomplete')).toBeVisible();
  await expect(page.getByLabel('Password', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: 'Return to sign in' }).click();
  await expect(page.getByRole('heading', { name: 'Staff sign in' })).toBeVisible();
});

test('legacy platform sign-in uses the shared accessible password control', async ({ page }) => {
  await page.route('**/api/v1/platform/auth/session', route => route.fulfill({ status: 401, json: {} }));
  await page.goto('/platform.html');
  const password = page.getByLabel('Password', { exact: true });
  await password.fill('local-password');
  await page.getByRole('button', { name: 'Show password' }).click();
  await expect(password).toHaveAttribute('type', 'text');
  await expect(password).toHaveValue('local-password');
});

test('scanner presents only server-confirmed structured outcomes', async ({ page }) => {
  await page.route('**/api/v1/gate/session', route => route.fulfill({ json: {
    role: 'gate_scanner', assignments: [{ event_id: 'event-1', event_name: 'Innovation Summit 2026',
      gate_id: 'gate-1', gate_name: 'Main hall', event_status: 'published' }],
  } }));
  await page.route('**/api/v1/auth/csrf', route => route.fulfill({ json: { csrf_token: 'csrf' } }));
  await page.route('**/api/v1/gate/redeem', async route => {
    const credential = String(route.request().postDataJSON().credential);
    const outcome = credential as 'duplicate' | 'revoked' | 'invalid';
    await route.fulfill({ json: { outcome, confirmed_at: '2026-11-01T09:10:00Z' } });
  });
  await page.goto('/gate.html');
  for (const [credential, heading] of [['duplicate', 'Already checked in'], ['revoked', 'Ticket revoked'], ['invalid', 'Ticket not accepted']] as const) {
    await page.getByLabel('Secure manual credential').fill(credential);
    await page.getByRole('button', { name: 'Verify with server' }).click();
    await expect(page.getByRole('heading', { name: heading })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Admission confirmed' })).toHaveCount(0);
    await page.getByRole('button', { name: 'Scan next ticket' }).click();
  }
});

test('reports, branding, and settings use honest connected and unavailable states', async ({ page }) => {
  await mockOrganizer(page);
  await page.goto('/workspace.html#reports?event=event-1');
  await expect(page.getByRole('heading', { name: 'Attendance export', level: 1 })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Additional report formats are coming soon' })).toBeVisible();
  await page.getByRole('link', { name: 'Branding' }).click();
  await expect(page.getByText('This workspace does not repeat a sample organization name')).toBeVisible();
  await expect(page.getByText('Summit Events')).toHaveCount(0);
  await page.getByRole('link', { name: 'Settings' }).click();
  await expect(page.getByRole('heading', { name: 'Profile editing is unavailable' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Self-service privacy operations are unavailable' })).toBeVisible();
});

test('phase 4 supporting screens reflow at 320px and pass automated WCAG checks', async ({ page }) => {
  await mockOrganizer(page);
  await page.route('**/api/v1/platform/auth/session', route => route.fulfill({ status: 401, json: {} }));
  for (const path of ['/reset', '/platform-console.html#privacy', '/workspace.html#reports?event=event-1', '/workspace.html#settings?event=event-1']) {
    await page.setViewportSize({ width: 320, height: 760 });
    await page.goto(path);
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag22aa']).analyze();
    expect(results.violations).toEqual([]);
  }
});

test('supporting-interface navigation restores focus and removes drawer motion', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 760 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.route('**/api/v1/platform/auth/session', route => route.fulfill({ status: 401, json: {} }));
  await page.goto('/platform-console.html#privacy');
  const trigger = page.getByRole('button', { name: 'Open navigation' });
  await trigger.focus();
  await page.keyboard.press('Enter');
  await expect(page.getByRole('complementary', { name: 'Platform navigation' }).getByRole('button', { name: 'Close navigation' })).toBeFocused();
  await expect(page.locator('.app-sidebar')).toHaveCSS('transition-duration', '0s');
  await page.keyboard.press('Escape');
  await expect(trigger).toBeFocused();
});

test('capture Phase 4 supporting interfaces at desktop, tablet, and mobile widths', async ({ page }, testInfo) => {
  test.setTimeout(90_000);
  const screenshotDir = '../docs/screenshots';

  await page.route('**/api/v1/platform/auth/session', route => route.fulfill({ json: {
    email: 'platform@example.test', permission: 'tenant.provision',
  } }));
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/platform-console.html#organizations');
  await expect(page.getByRole('heading', { name: 'Create organization' })).toBeVisible();
  const platformShot = `${screenshotDir}/phase4-platform-organizations-desktop.png`;
  await page.screenshot({ path: platformShot, fullPage: true, animations: 'disabled' });
  await testInfo.attach('phase4-platform-organizations-desktop', { path: platformShot, contentType: 'image/png' });

  await mockOrganizer(page);
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.goto('/workspace.html#reports?event=event-1');
  await expect(page.getByRole('heading', { name: 'Attendance export', level: 1 })).toBeVisible();
  const reportsShot = `${screenshotDir}/phase4-reports-tablet.png`;
  await page.screenshot({ path: reportsShot, fullPage: true, animations: 'disabled' });
  await testInfo.attach('phase4-reports-tablet', { path: reportsShot, contentType: 'image/png' });

  await page.route('**/api/v1/shared/context', route => route.fulfill({ json: { shared: false } }));
  await page.route('**/api/v1/auth/session', route => route.fulfill({ status: 401, json: {} }));
  await page.setViewportSize({ width: 320, height: 760 });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Staff sign in' })).toBeVisible();
  const authShot = `${screenshotDir}/phase4-auth-mobile-320.png`;
  await page.screenshot({ path: authShot, fullPage: true, animations: 'disabled' });
  await testInfo.attach('phase4-auth-mobile-320', { path: authShot, contentType: 'image/png' });

  await page.route('**/api/v1/gate/session', route => route.fulfill({ json: {
    role: 'gate_scanner', assignments: [{ event_id: 'event-1', event_name: 'Innovation Summit 2026',
      gate_id: 'gate-1', gate_name: 'Main hall', event_status: 'published' }],
  } }));
  await page.route('**/api/v1/auth/csrf', route => route.fulfill({ json: { csrf_token: 'csrf' } }));
  await page.route('**/api/v1/gate/redeem', route => route.fulfill({ json: {
    outcome: 'invalid', confirmed_at: '2026-11-01T09:10:00Z',
  } }));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/gate.html');
  await page.getByLabel('Secure manual credential').fill('unrecognized-ticket');
  await page.getByRole('button', { name: 'Verify with server' }).click();
  await expect(page.getByRole('heading', { name: 'Ticket not accepted' })).toBeVisible();
  const gateShot = `${screenshotDir}/phase4-gate-invalid-mobile.png`;
  await page.screenshot({ path: gateShot, fullPage: true, animations: 'disabled' });
  await testInfo.attach('phase4-gate-invalid-mobile', { path: gateShot, contentType: 'image/png' });
});
