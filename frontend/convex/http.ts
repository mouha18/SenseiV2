import { httpRouter } from "convex/server";
import { httpAction } from "./_generated/server";
import { auth } from "./auth";
import { internal } from "./_generated/api";

const http = httpRouter();

auth.addHttpRoutes(http);

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let mismatch = 0;
  for (let i = 0; i < a.length; i++) {
    mismatch |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return mismatch === 0;
}

// Seed of Sprint 4's `getRequestContext` (INTERNAL_API.md): for now this only
// resolves the revocation clock for `get_current_user` (ADR-0003). Sprint 4
// extends this same endpoint to fold in velocity/key/session/history instead
// of adding a second one.
http.route({
  path: "/authState",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    const serviceSecret = request.headers.get("X-Service-Secret") ?? "";
    const expected = process.env.CONVEX_SERVICE_SECRET ?? "";
    if (!expected || !timingSafeEqual(serviceSecret, expected)) {
      return new Response("Unauthorized", { status: 401 });
    }

    const { userId } = (await request.json()) as { userId: string };
    const tokensValidAfter = await ctx.runQuery(
      internal.users_internal.getTokensValidAfter,
      { userId },
    );
    if (tokensValidAfter === null) {
      return new Response("Not found", { status: 404 });
    }

    return new Response(JSON.stringify({ tokensValidAfter }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  }),
});

export default http;
