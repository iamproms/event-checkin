import { proxyToRender } from '../lib/render-proxy.js';

export const config = { api: { bodyParser: false } };

export default async function handler(request, response) {
  const path = Array.isArray(request.query.path) ? request.query.path.join('/') : request.query.path;
  const query = new URL(request.url, 'https://proxy.invalid').search;
  await proxyToRender(request, response, `/api/${path || ''}${query}`);
}
