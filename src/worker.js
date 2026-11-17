// Runs in front of the static assets so every URL has exactly one canonical form,
// reached with a permanent (301) redirect.
const CANONICAL_HOST = "pubnamestats.co.uk";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // 1. One host, always HTTPS: www, *.workers.dev and http all 301 to https://pubnamestats.co.uk
    const isLocal = url.hostname === "localhost" || url.hostname === "127.0.0.1"; // `wrangler dev`
    if (!isLocal && (url.hostname !== CANONICAL_HOST || url.protocol !== "https:")) {
      url.protocol = "https:";
      url.hostname = CANONICAL_HOST;
      url.port = "";
      return Response.redirect(url.toString(), 301);
    }

    // 2. Lowercase paths (all generated URLs are lowercase).
    if (url.pathname !== url.pathname.toLowerCase()) {
      url.pathname = url.pathname.toLowerCase();
      return Response.redirect(url.toString(), 301);
    }

    const response = await env.ASSETS.fetch(request);

    // 3. The assets layer adds/removes trailing slashes and drops /index.html with a 307.
    //    Make those permanent.
    if (response.status === 307 || response.status === 308) {
      const location = new URL(response.headers.get("Location"), url);
      location.search = url.search;
      return Response.redirect(location.toString(), 301);
    }

    const headers = new Headers(response.headers);
    headers.set("X-Content-Type-Options", "nosniff");
    headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
    if (url.pathname === "/names.json") headers.set("X-Robots-Tag", "noindex");
    return new Response(response.body, { status: response.status, statusText: response.statusText, headers });
  },
};
