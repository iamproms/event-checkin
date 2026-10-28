import { isIP } from 'node:net';

const REQUEST_HEADERS = ['accept', 'content-type', 'cookie', 'origin', 'user-agent', 'x-csrf-token'];
const RESPONSE_HEADERS = ['cache-control', 'content-disposition', 'content-type', 'referrer-policy', 'x-content-type-options'];
const MAX_REQUEST_BYTES = 12 * 1024 * 1024;

function singleHeader(value) {
  return Array.isArray(value) ? value[0] : value;
}

async function body(request) {
  if (request.method === 'GET' || request.method === 'HEAD') return undefined;
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > MAX_REQUEST_BYTES) throw new Error('REQUEST_TOO_LARGE');
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

export async function proxyToRender(request, response, targetPath) {
  const origin = process.env.RENDER_API_ORIGIN;
  const originSecret = process.env.ORIGIN_AUTH_SECRET;
  if (!origin?.startsWith('https://') || !originSecret) {
    response.status(503).json({ detail: { code: 'ORIGIN_UNAVAILABLE' } });
    return;
  }
  const publicHost = singleHeader(request.headers.host)?.toLowerCase();
  const clientIp = singleHeader(request.headers['x-real-ip']);
  if (!publicHost || !/^[a-z0-9.-]+$/.test(publicHost) || !clientIp || !isIP(clientIp)) {
    response.status(400).json({ detail: { code: 'INVALID_INGRESS' } });
    return;
  }
  const headers = {};
  for (const name of REQUEST_HEADERS) {
    const value = singleHeader(request.headers[name]);
    if (value) headers[name] = value;
  }
  headers['x-eventcheckin-origin-auth'] = originSecret;
  headers['x-eventcheckin-public-host'] = publicHost;
  headers['x-eventcheckin-client-ip'] = clientIp;
  try {
    const upstream = await fetch(new URL(targetPath, origin), {
      method: request.method,
      headers,
      body: await body(request),
      redirect: 'manual',
    });
    response.status(upstream.status);
    for (const name of RESPONSE_HEADERS) {
      const value = upstream.headers.get(name);
      if (value) response.setHeader(name, value);
    }
    const cookies = upstream.headers.getSetCookie?.() || [];
    if (cookies.length) response.setHeader('set-cookie', cookies);
    response.send(Buffer.from(await upstream.arrayBuffer()));
  } catch (error) {
    const status = error instanceof Error && error.message === 'REQUEST_TOO_LARGE' ? 413 : 502;
    response.status(status).json({ detail: { code: status === 413 ? 'REQUEST_TOO_LARGE' : 'ORIGIN_UNAVAILABLE' } });
  }
}
