import assert from 'node:assert/strict';
import { test } from 'node:test';
import { loadConfigFromFile } from 'vite';

test('local Vite proxy retains the browser authority and strips forwarded headers', async () => {
  const loaded = await loadConfigFromFile(
    { command: 'serve', mode: 'development' },
    'vite.config.ts',
  );
  assert.ok(loaded);
  const server = loaded.config.server;
  assert.deepEqual(server.allowedHosts, ['platform.local.example.test']);
  for (const route of ['/api', '/health', '/ready']) {
    const options = server.proxy[route];
    assert.equal(options.changeOrigin, false);
    const handlers = new Map();
    options.configure({ on(event, handler) { handlers.set(event, handler); } });
    const removed = [];
    const set = [];
    handlers.get('proxyReq')(
      {
        removeHeader(header) { removed.push(header); },
        setHeader(header, value) { set.push([header, value]); },
      },
      { headers: { host: 'platform.local.example.test:8443' } },
    );
    assert.deepEqual(removed, [
      'forwarded', 'x-forwarded-host', 'x-forwarded-for', 'x-forwarded-proto',
    ]);
    assert.deepEqual(set, [['host', 'platform.local.example.test:8443']]);
  }
});
