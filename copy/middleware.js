// ---------------------------------------------------------------------------
// middleware.js: the one difference between copy A (bot check on) and copy B (bot check off).
//
// Both copies deploy this same directory of captured pages. The deployment's AXIS_VARIANT env var
// picks the behaviour:
//   a  "bot check on": mirrors what live arbitrum.io returns to curl or an agent's fetch (checked
//      2 Nov 2026): HTTP 403 with Cloudflare's "Just a moment..." managed-challenge page and the
//      `cf-mitigated: challenge` header. Live returns that whatever the user agent, even a browser UA,
//      because the check is a JavaScript challenge a plain HTTP client can't run; so A does the same
//      for every request. Exception, as live: /robots.txt is served normally (live gives it 200).
//   b  "bot check off": every page is served as captured.
// Live /arbitrum-101 redirects to / (seen in the browser); B mirrors that with a 307 (the exact live
// status is hidden behind the challenge; 307 is Next.js' default for redirect()). A gives it the 403
// like any other path.
//
// challenge.js is NOT in this repo. Ours exported live arbitrum.io's 403 body verbatim, which is
// Cloudflare's page, not ours to publish. To build your own copy, save what live returns to a plain
// fetch (e.g. `curl -s https://arbitrum.io/`) and export it: `export default "<!DOCTYPE html>...";`
//
// Every request logs one JSON line (variant, path, Accept, user agent, what was served). Read from the
// deployment's runtime logs, that line is the proof of what each run's fetches got (scripts/fetch-runs.py).
//
// Why middleware: Vercel serves an existing static file before it applies rewrites, so only Routing
// Middleware can refuse a page that exists.
//
// Deploy twice from the same files, as previews:
//   vercel deploy --environment preview --env AXIS_VARIANT=a   -> {COPY_A}
//   vercel deploy --environment preview --env AXIS_VARIANT=b   -> {COPY_B}
// ---------------------------------------------------------------------------

import { next } from '@vercel/functions';
import CHALLENGE from './challenge.js';

const VARIANT = (process.env.AXIS_VARIANT || 'a').toLowerCase() === 'b' ? 'b' : 'a';
// Build files that sit in the deploy directory but aren't part of the site.
const INTERNAL = new Set(['/challenge.js', '/middleware.js', '/package.json', '/pnpm-lock.yaml', '/vercel.json']);

export const config = {
  matcher: ['/', '/:path*'],
};

export default function middleware(request) {
  const url = new URL(request.url);
  const path = url.pathname;
  let served;
  let response;

  if (VARIANT === 'a' && path !== '/robots.txt') {
    served = 'challenge-403';
    response = new Response(CHALLENGE, {
      status: 403,
      headers: {
        'content-type': 'text/html; charset=UTF-8',
        'cf-mitigated': 'challenge',
        'cache-control': 'private, max-age=0, no-store, no-cache, must-revalidate',
        // vercel.json headers may not reach a middleware-made response; set it here too.
        'x-robots-tag': 'noindex, nofollow, noarchive',
      },
    });
  } else if (INTERNAL.has(path)) {
    served = 'internal-404';
    response = new Response('Not found', { status: 404, headers: { 'x-robots-tag': 'noindex, nofollow, noarchive' } });
  } else if (path === '/arbitrum-101' || path === '/arbitrum-101/') {
    served = 'redirect';
    response = new Response(null, {
      status: 307,
      headers: { location: '/', 'x-robots-tag': 'noindex, nofollow, noarchive' },
    });
  } else {
    served = path === '/robots.txt' ? 'robots' : 'page';
    response = next();
  }

  console.log(JSON.stringify({
    // 'pt3' was our working name for this test (now axis-arbitrum). We kept it so this file matches the
    // copies that ran; scripts/fetch-runs.py picks out request lines by this tag, so change both together.
    axis: 'pt3',
    variant: VARIANT,
    path,
    accept: request.headers.get('accept') || '',
    ua: request.headers.get('user-agent') || '',
    served,
  }));
  return response;
}
