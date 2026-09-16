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
 *
 * THE ONE EXCEPTION IS A SEND THAT NEVER GOT A REFUSAL TO FORWARD, below. There
 * the handler has to write its own sentence because no other one exists, and
 * the rule that applies instead is that it may not assert a cause it has not
 * observed.
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

/**
 * Every layer of an error, because the outermost one is never the informative
 * one. `String(err)` on a failed fetch yields "TypeError: fetch failed" and
 * stops; the sentence that identifies the failure is on `err.cause`, so
 * stringifying the outer error reported the symptom and discarded the finding.
 */
function causes(error: unknown): string[] {
  const chain: string[] = [];
  // Bounded because a cause chain is free to be circular and this runs on the
  // path where something has already gone wrong.
  for (let at: unknown = error; at && chain.length < 5;
       at = (at as { cause?: unknown }).cause) {
    chain.push(String(at));
  }
  return chain;
}

/**
 * Whether the backend is answering at all, asked without a credential.
 *
 * `/api/health` is the one endpoint the key middleware never gates, because a
 * liveness probe that needs a credential reports down whenever the credential
 * is wrong. That makes it the only honest way to separate "nothing is
 * listening" from "listening, and it refused". It also reports whether a key is
 * required — never the key — which is the likeliest reason a request died
 * before its body finished. `TestTheOptionalApiKey` in `tests/test_api.py` pins
 * both properties, so this handler is reading a contract rather than a habit.
 */
async function health() {
  let response: Response;
  try {
    response = await fetch(`${backend()}/api/health`, { cache: 'no-store' });
  } catch {
    return null;
  }
  try {
    const body = await response.json() as { requires_api_key?: unknown };
    if (response.ok && typeof body.requires_api_key === 'boolean') {
      return { isThisApi: true as const, requiresKey: body.requires_api_key };
    }
  } catch { /* It answered. It just did not answer with this API's health. */ }
  // Something holds the address and it is not the scoring API, which is worth
  // saying: it is a different mistake from nothing being there.
  return { isThisApi: false as const };
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
  } catch (send) {
    // THE SEND THREW, WHICH IS NOT THE SAME AS NOBODY ANSWERING, and this
    // branch used to assert the second whenever the first happened. A backend
    // that refuses before reading the body it is still being sent — a 401 from
    // the key middleware is exactly that — makes the send throw instead of
    // returning the refusal, so a live API that answered was reported as an
    // address that did not. Nobody reading "did not answer" checks a
    // credential, and the real refusal said to check one.
    //
    // So ask, rather than guess. This is a separate question put to a different
    // endpoint, not a retry: the request is gone, its body was consumed by the
    // send that failed, and replaying it is not this handler's call to make.
    const alive = await health();
    const cause = causes(send);
    if (alive === null) {
      // NAMES THE ADDRESS AND WHOSE IT IS. On a deployed page the default
      // points at the server's own loopback, which is nobody's backend.
      return Response.json({ detail: {
        error: `The scoring API did not answer at ${backend()}.`,
        fix: process.env.SEA_API_URL
          ? 'Check that the backend is running and reachable from this '
            + 'deployment.'
          : 'This deployment has no SEA_API_URL set, so it is trying its own '
            + 'loopback address. Set SEA_API_URL to where the backend is '
            + 'running; it is read at request time, so no redeploy is needed.',
        cause,
      } }, { status: 502 });
    }
    if (!alive.isThisApi) {
      return Response.json({ detail: {
        error: `Something is answering at ${backend()}, but it is not the `
             + 'scoring API.',
        fix: 'Its /api/health did not answer the way this API does. Check '
           + 'SEA_API_URL for a port or a host belonging to something else.',
        cause,
      } }, { status: 502 });
    }
    // It is up, it is this API, and the send still died: the refusal it wrote
    // was lost with the connection. Say that, and say what to check — without
    // claiming to know what it would have said.
    return Response.json({ detail: {
      error: `The scoring API is running at ${backend()}, but this request `
           + 'failed while its body was still being sent, so whatever it '
           + 'answered did not survive.',
      fix: !alive.requiresKey
        ? 'It requires no API key, so a credential is not the cause. The chain '
          + 'below is what the send itself reported.'
        : process.env.SEA_API_KEY
          ? 'It requires an API key and this deployment sends one, so the two '
            + 'disagree. Compare SEA_API_KEY here against the value the '
            + 'backend was started with.'
          : 'It requires an API key and this deployment has no SEA_API_KEY '
            + 'set, so every request is refused before it is read. Set '
            + "SEA_API_KEY here to the backend's value.",
      cause,
    } }, { status: 502 });
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
