import { proxyToRender } from '../lib/render-proxy.js';

export default async function handler(request, response) {
  if (request.method !== 'GET') return response.status(405).end();
  await proxyToRender(request, response, '/ready');
}
