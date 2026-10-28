import assert from 'node:assert/strict';
import test from 'node:test';

import { proxyToRender } from '../lib/render-proxy.js';

class Reply {
  headers = {};
  statusCode = 200;
  payload = null;

  status(value) { this.statusCode = value; return this; }
  json(value) { this.payload = value; return this; }
  setHeader(name, value) { this.headers[name.toLowerCase()] = value; }
  send(value) { this.payload = value; }
}

function request(chunks = []) {
  return {
    method: chunks.length ? 'POST' : 'GET',
    url: '/api/v1/test?safe=1',
    headers: {
      host: 'platform.events.example.test',
      'x-real-ip': '203.0.113.8',
      accept: 'application/json',
      authorization: 'must-not-forward',
      cookie: '__Host-session=opaque',
      origin: 'https://platform.events.example.test',
      'x-csrf-token': 'opaque-csrf',
      'content-type': 'application/json',
    },
    async *[Symbol.asyncIterator]() { for (const chunk of chunks) yield chunk; },
  };
}

test('production proxy fails closed when origin configuration is absent', async () => {
  const previousOrigin = process.env.RENDER_API_ORIGIN;
  const previousSecret = process.env.ORIGIN_AUTH_SECRET;
  delete process.env.RENDER_API_ORIGIN;
  delete process.env.ORIGIN_AUTH_SECRET;
  const reply = new Reply();
  await proxyToRender(request(), reply, '/ready');
  assert.equal(reply.statusCode, 503);
  assert.equal(reply.payload.detail.code, 'ORIGIN_UNAVAILABLE');
  if (previousOrigin) process.env.RENDER_API_ORIGIN = previousOrigin;
  if (previousSecret) process.env.ORIGIN_AUTH_SECRET = previousSecret;
});

test('production proxy forwards only approved browser and private ingress headers', async () => {
  process.env.RENDER_API_ORIGIN = 'https://origin.example.test';
  process.env.ORIGIN_AUTH_SECRET = 'synthetic-origin-secret';
  const originalFetch = globalThis.fetch;
  let captured;
  globalThis.fetch = async (url, options) => {
    captured = { url: String(url), options };
    return new Response('{"ok":true}', {
      status: 200,
      headers: {
        'content-type': 'application/json',
        'set-cookie': '__Host-session=opaque; Secure; HttpOnly; SameSite=Strict',
      },
    });
  };
  try {
    const reply = new Reply();
    await proxyToRender(request([Buffer.from('{"safe":true}')]), reply, '/api/v1/test?safe=1');
    assert.equal(captured.url, 'https://origin.example.test/api/v1/test?safe=1');
    assert.equal(captured.options.headers.authorization, undefined);
    assert.equal(captured.options.headers.cookie, '__Host-session=opaque');
    assert.equal(captured.options.headers['x-eventcheckin-origin-auth'], 'synthetic-origin-secret');
    assert.equal(captured.options.headers['x-eventcheckin-public-host'], 'platform.events.example.test');
    assert.equal(captured.options.headers['x-eventcheckin-client-ip'], '203.0.113.8');
    assert.equal(String(captured.options.body), '{"safe":true}');
    assert.equal(reply.statusCode, 200);
    assert.match(String(reply.headers['set-cookie']), /__Host-session/);
  } finally {
    globalThis.fetch = originalFetch;
  }
});

test('production proxy rejects oversized bodies before contacting Render', async () => {
  process.env.RENDER_API_ORIGIN = 'https://origin.example.test';
  process.env.ORIGIN_AUTH_SECRET = 'synthetic-origin-secret';
  const originalFetch = globalThis.fetch;
  let called = false;
  globalThis.fetch = async () => { called = true; throw new Error('unexpected'); };
  try {
    const reply = new Reply();
    await proxyToRender(request([Buffer.alloc(12 * 1024 * 1024 + 1)]), reply, '/api/v1/import');
    assert.equal(called, false);
    assert.equal(reply.statusCode, 413);
    assert.equal(reply.payload.detail.code, 'REQUEST_TOO_LARGE');
  } finally {
    globalThis.fetch = originalFetch;
  }
});
