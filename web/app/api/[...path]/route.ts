/**
 * The scoring API, reached through this deployment rather than directly.
 *
 * WHY A PROXY AT ALL. A static frontend ships its environment to every visitor:
 * anything named `NEXT_PUBLIC_*` is readable in the bundle, so a key put there
 * is not a key. This handler runs on the server, holds `SEA_API_KEY`, and the
 * browser never sees it. It is the only way a public page can talk to a
 * credentialed backend without handing the credential out.
 *
 * IT ALSO FIXES THE TRAP THAT CAUSED THIS. `NEXT_PUBLIC_API_BASE` is inlined at
 * BUILD time, so setting it in a dashboard does nothing until something
 * redeploys — the setting looks right, the page stays broken, and nothing
 * connects the two. `SEA_API_URL` is read HERE, at request time, so changing it
 * takes effect on the next request. The build-time variable survives as an
 * escape hatch for talking to a backend directly, and is no longer the
 * mechanism.
 *
 * WHAT IT DELIBERATELY DOES NOT DO. It does not interpret, cache, retry or
 * reshape anything. The status, the body and the content type come back exactly
 * as the backend sent them, because every refusal this API makes is a sentence
 * somebody needs to read: the file and column that failed the contract, the
 * reason a decision was refused. A proxy that turned those into its own error
 * would throw away the useful half.
 */
import { NextRequest } from 'next/server';

// Read per request, never at module load: a host that changes an environment
// variable expects the change to take effect, and a module-level capture would
// pin it to whenever the function cold-started.
function backend() {
  return (process.env.SEA_API_URL ?? 'http://127.0.0.1:8000')
    .replace(/\/+$/, '');
}

function outboundHeaders(request: NextRequest) {
  const headers = new Headers();
  const type = request.headers.get('content-type');
  if (type) headers.set('content-type', type);
  const key = process.env.SEA_API_KEY;
  if (key) headers.set('X-API-Key', key);
  return headers;
}

async function forward(request: NextRequest, path: string[]) {
  const target = `${backend()}/api/${path.join('/')}${request.nextUrl.search}`;
  let response: Response;
  try {
    response = await fetch(target, {
      method: request.method,
      headers: outboundHeaders(request),
      // Streamed rather than buffered, so a large upload is not read into this
      // function's memory on its way past.
      body: request.method === 'GET' ? undefined : request.body,
      // Required by undici whenever a stream is used as a body.
      duplex: 'half',
      cache: 'no-store',
    } as RequestInit & { duplex: 'half' });
  } catch (unreachable) {
    // NAMES THE ADDRESS AND WHOSE IT IS. On a deployed page the default points
    // at the server's own loopback, which is nobody's backend.
    return Response.json({
      detail: {
        error: `The scoring API did not answer at ${backend()}.`,
        fix: process.env.SEA_API_URL
          ? 'Check that the backend is running and reachable from this '
            + 'deployment.'
          : 'This deployment has no SEA_API_URL set, so it is trying its own '
            + 'loopback address. Set SEA_API_URL to where the backend is '
            + 'running; it is read at request time, so no redeploy is needed.',
        cause: String(unreachable),
      },
    }, { status: 502 });
  }

  // Verbatim. See the note above on why nothing here reshapes a refusal.
  const headers = new Headers();
  const type = response.headers.get('content-type');
  if (type) headers.set('content-type', type);
  return new Response(response.body, {
    status: response.status,
    headers,
  });
}

type Params = { params: Promise<{ path: string[] }> };

export async function GET(request: NextRequest, { params }: Params) {
  return forward(request, (await params).path);
}

export async function POST(request: NextRequest, { params }: Params) {
  return forward(request, (await params).path);
}

// Not static: it holds a secret and reads the environment per request.
export const dynamic = 'force-dynamic';
