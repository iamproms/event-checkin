import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { eventLocal, eventUtc } from '../src/event-time';
import { describeEvent } from '../src/event-vocabulary';

const draft = {
  id: '51f8f356-a31e-45cc-b7f8-6130f90d1bc7', slug: 'ajo-lagos', name: 'Àjọ Lagos 2026',
  status: 'draft', revision: 1, starts_at: '2026-11-03T09:00:00+00:00',
  ends_at: '2026-11-03T17:00:00+00:00', timezone: 'Africa/Lagos', location: 'Victoria Island',
  registration_opens_at: '2026-10-25T09:00:00+00:00',
  registration_closes_at: '2026-11-03T09:00:00+00:00',
  checkin_opens_at: '2026-11-03T09:00:00+00:00',
  checkin_closes_at: '2026-11-03T17:00:00+00:00',
  form_schema: { fields: [] }, form_schema_version: 1,
  pii_purge_due_at: '2027-02-01T17:00:00+00:00',
};

test('event-local dates convert without device-zone or DST guessing', () => {
  expect(eventUtc('2026-11-03T09:00', 'Africa/Lagos')).toBe('2026-11-03T08:00:00.000Z');
  expect(eventLocal('2026-11-03T08:00:00Z', 'Africa/Lagos')).toBe('2026-11-03T09:00');
  expect(() => eventUtc('2026-03-08T02:30', 'America/New_York')).toThrow('does not occur');
  expect(() => eventUtc('2026-11-01T01:30', 'America/New_York')).toThrow('repeats');
  expect(describeEvent('cancelled')).toEqual({ title: 'Cancelled', tone: 'danger',
    instruction: 'Cancellation is final. This event cannot reopen.' });
});

test('event configuration is readable, accessible and reflows at 320px and 200% text', async ({ page }) => {
  await page.route('**/api/v1/events', (route) => route.fulfill({ json: { events: [draft] } }));
  await page.route('**/api/v1/events/*/gates', (route) => route.fulfill({
    json: { gates: [{ id: '1e34e24e-b8cd-4d96-a154-cad10484f28b', name: 'Main entrance', enabled: true }] },
  }));
  await page.route('**/api/v1/events/*/readiness', (route) => route.fulfill({ json: { ready: true, instructions: [] } }));
  await page.goto('/events.html');
  await expect(page.getByRole('heading', { name: 'Events', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Open event' }).click();
  await expect(page.getByRole('heading', { name: 'Àjọ Lagos 2026' })).toBeVisible();
  await page.getByRole('link', { name: 'Readiness' }).click();
  await expect(page.getByText('Ready to publish')).toBeVisible();
  await page.getByRole('button', { name: 'Publish event' }).click();
  await expect(page.getByRole('dialog', { name: 'Publish event?' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Publish event' })).toBeFocused();
  for (const theme of ['light', 'dark']) {
    if (theme === 'dark') await page.getByRole('button', { name: 'Use dark theme' }).click();
    await page.setViewportSize({ width: 320, height: 740 });
    await page.evaluate(() => { document.documentElement.style.fontSize = '200%'; });
    for (const panel of ['Readiness', 'Gates', 'Form', 'Settings']) {
      await page.getByRole('link', { name: panel }).click();
      expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320);
      const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag22aa']).analyze();
      expect(results.violations).toEqual([]);
    }
  }
});

test('draft editor uses versioned API, CSRF and reports concurrency errors', async ({ page }) => {
  let formWrites = 0;
  await page.route('**/api/v1/events', (route) => route.fulfill({ json: { events: [draft] } }));
  await page.route('**/api/v1/events/*/gates', (route) => route.fulfill({ json: { gates: [] } }));
  await page.route('**/api/v1/events/*/readiness', (route) =>
    route.fulfill({ json: { ready: false, instructions: ['Enable at least one gate.'] } }));
  await page.route('**/api/v1/auth/csrf', (route) => route.fulfill({ json: { csrf_token: 'fixture' } }));
  await page.route('**/api/v1/events/*/form', (route) => {
    formWrites += 1;
    expect(route.request().method()).toBe('PUT');
    expect(route.request().headers()['x-csrf-token']).toBe('fixture');
    expect(route.request().postDataJSON()).toMatchObject({ revision: 1,
      form_schema: { fields: [{ key: 'meal', label: 'Meal', type: 'text', required: false }] } });
    return route.fulfill({ status: 409, json: { detail: { code: 'EVENT_CONFLICT', message: 'Conflict' } } });
  });
  await page.goto('/events.html');
  await page.getByRole('button', { name: 'Open event' }).click();
  await page.getByRole('link', { name: 'Form' }).click();
  await page.getByRole('button', { name: 'Add question' }).click();
  await page.getByRole('textbox', { name: 'Field key' }).fill('meal');
  await page.getByRole('textbox', { name: 'Question label' }).fill('Meal');
  await page.getByRole('button', { name: 'Save new version' }).click();
  await expect(page.getByRole('alert')).toContainText('This event changed');
  expect(formWrites).toBe(1);
});

test('published name edit preserves exact schedule instants', async ({ page }) => {
  const published = { ...draft, status: 'published', timezone: 'America/New_York',
    starts_at: '2026-11-01T01:30:15-04:00', ends_at: '2026-11-01T02:30:45-05:00' };
  let submitted = false;
  await page.route('**/api/v1/events', (route) => route.fulfill({ json: { events: [published] } }));
  await page.route('**/api/v1/events/*/gates', (route) => route.fulfill({ json: { gates: [] } }));
  await page.route('**/api/v1/events/*/readiness', (route) => route.fulfill({ json: { ready: true, instructions: [] } }));
  await page.route('**/api/v1/auth/csrf', (route) => route.fulfill({ json: { csrf_token: 'fixture' } }));
  await page.route(`**/api/v1/events/${published.id}`, (route) => {
    const body = route.request().postDataJSON();
    expect(body.starts_at).toBe(published.starts_at);
    expect(body.ends_at).toBe(published.ends_at);
    expect(body.name).toBe('Updated event name');
    submitted = true;
    return route.fulfill({ json: { ...published, name: body.name } });
  });
  await page.goto('/events.html');
  await page.getByRole('button', { name: 'Open event' }).click();
  await page.getByRole('link', { name: 'Settings' }).click();
  await page.getByRole('textbox', { name: 'Event name' }).fill('Updated event name');
  await page.getByRole('button', { name: 'Save settings' }).click();
  await expect(page.getByText('Event settings saved.')).toBeVisible();
  expect(submitted).toBe(true);
});
