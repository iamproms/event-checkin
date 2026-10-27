/**
 * Candidate staging ingress only. G-06 approval and an owned zone are required.
 * Bind ORIGIN_AUTH_SECRET with `wrangler secret put`; never put it in wrangler.toml.
 */
export default {
  async fetch(request, env) {
    const publicUrl = new URL(request.url);
    const clientIp = request.headers.get("CF-Connecting-IP");
    if (!clientIp || !env.RENDER_ORIGIN_HOST || !env.ORIGIN_AUTH_SECRET) {
      return new Response("Ingress unavailable", { status: 503 });
    }

    const originUrl = new URL(request.url);
    originUrl.protocol = "https:";
    originUrl.hostname = env.RENDER_ORIGIN_HOST;
    originUrl.port = "";

    const headers = new Headers(request.headers);
    headers.delete("Forwarded");
    headers.delete("X-Forwarded-For");
    headers.delete("X-Forwarded-Host");
    headers.delete("X-Eventcheckin-Origin-Auth");
    headers.delete("X-Eventcheckin-Public-Host");
    headers.delete("X-Eventcheckin-Client-IP");
    headers.set("X-Eventcheckin-Origin-Auth", env.ORIGIN_AUTH_SECRET);
    headers.set("X-Eventcheckin-Public-Host", publicUrl.hostname);
    headers.set("X-Eventcheckin-Client-IP", clientIp);

    return fetch(
      new Request(originUrl, {
        method: request.method,
        headers,
        body: request.body,
        redirect: "manual",
      }),
    );
  },
};
