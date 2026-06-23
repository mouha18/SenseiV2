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

function isAuthorized(request: Request): boolean {
  const serviceSecret = request.headers.get("X-Service-Secret") ?? "";
  const expected = process.env.CONVEX_SERVICE_SECRET ?? "";
  return expected !== "" && timingSafeEqual(serviceSecret, expected);
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// Seed of Sprint 4's `getRequestContext` (INTERNAL_API.md): for now this only
// resolves the revocation clock for `get_current_user` (ADR-0003). Sprint 4
// extends this same endpoint to fold in velocity/key/session/history instead
// of adding a second one.
http.route({
  path: "/authState",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return new Response("Unauthorized", { status: 401 });

    const { userId } = (await request.json()) as { userId: string };
    const tokensValidAfter = await ctx.runQuery(
      internal.users_internal.getTokensValidAfter,
      { userId },
    );
    if (tokensValidAfter === null) {
      return new Response("Not found", { status: 404 });
    }

    return json({ tokensValidAfter });
  }),
});

// Sprint 3 ingestion surface (ADR-0005/0011, INTERNAL_API.md "Ingestion").
// FastAPI never writes Convex directly (ADR-0003/0010) — these purpose-built
// routes are the only way it can create/update `documents` or lock/update a
// session's scope and storage totals.

http.route({
  path: "/sessions/ingestContext",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return new Response("Unauthorized", { status: 401 });
    const { sessionId } = (await request.json()) as { sessionId: string };
    const result = await ctx.runQuery(internal.sessions_internal.getIngestContext, { sessionId });
    if (result === null) return new Response("Not found", { status: 404 });
    return json(result);
  }),
});

http.route({
  path: "/sessions/lockScope",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return new Response("Unauthorized", { status: 401 });
    const body = (await request.json()) as {
      sessionId: string;
      scope: string;
      scopeDescription?: string;
      scopeSource: string;
    };
    try {
      await ctx.runMutation(internal.sessions_internal.lockSessionScope, body);
    } catch (err) {
      return json({ error: (err as Error).message }, 400);
    }
    return json({ locked: true });
  }),
});

http.route({
  path: "/sessions/updateTotals",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return new Response("Unauthorized", { status: 401 });
    const body = (await request.json()) as {
      sessionId: string;
      chunkDelta: number;
      storageDelta: number;
    };
    try {
      await ctx.runMutation(internal.sessions_internal.updateSessionTotals, body);
    } catch (err) {
      return json({ error: (err as Error).message }, 400);
    }
    return json({ updated: true });
  }),
});

http.route({
  path: "/documents/create",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return new Response("Unauthorized", { status: 401 });
    const body = (await request.json()) as {
      sessionId: string;
      userId: string;
      fileName: string;
      fileSizeBytes: number;
      storagePath: string;
    };
    try {
      const documentId = await ctx.runMutation(internal.documents_internal.createDocument, body);
      return json({ documentId });
    } catch (err) {
      return json({ error: (err as Error).message }, 400);
    }
  }),
});

http.route({
  path: "/documents/updateStatus",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return new Response("Unauthorized", { status: 401 });
    const body = (await request.json()) as {
      documentId: string;
      status: string;
      chunkCount?: number;
      error?: string;
    };
    try {
      await ctx.runMutation(internal.documents_internal.updateDocumentStatus, body);
    } catch (err) {
      return json({ error: (err as Error).message }, 400);
    }
    return json({ updated: true });
  }),
});

// Sprint 4 chat surface (ADR-0001/0004/0010, INTERNAL_API.md "FastAPI -> Convex").
// Same purpose-built-route rule as the ingestion endpoints above.

http.route({
  path: "/chat/requestContext",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return new Response("Unauthorized", { status: 401 });
    const body = (await request.json()) as {
      userId: string;
      sessionId: string;
      recentMessageLimit: number;
    };
    try {
      const result = await ctx.runMutation(internal.chat_internal.getRequestContext, body);
      return json(result);
    } catch (err) {
      return json({ error: (err as Error).message }, 404);
    }
  }),
});

http.route({
  path: "/chat/consumeAllowance",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return new Response("Unauthorized", { status: 401 });
    const body = (await request.json()) as { userId: string };
    try {
      const result = await ctx.runMutation(internal.chat_internal.consumeAllowance, body);
      return json(result);
    } catch (err) {
      return json({ error: (err as Error).message }, 404);
    }
  }),
});

http.route({
  path: "/chat/persistTurn",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return new Response("Unauthorized", { status: 401 });
    const body = (await request.json()) as {
      sessionId: string;
      userId: string;
      userMessage: { content: string };
      outcome: string;
      assistantMessage?: { content: string; responseType: string; source?: string };
      refundAllowance: boolean;
    };
    try {
      const result = await ctx.runMutation(internal.chat_internal.persistTurn, body);
      return json(result);
    } catch (err) {
      return json({ error: (err as Error).message }, 404);
    }
  }),
});

// Sprint 5 Feynman surface (ADR-0007/0010, INTERNAL_API.md "persistFeynman").
// chat/requestContext and chat/consumeAllowance are reused as-is for Feynman
// (both already generic, not chat-specific) — only the score write differs.

http.route({
  path: "/feynman/persist",
  method: "POST",
  handler: httpAction(async (ctx, request) => {
    if (!isAuthorized(request)) return new Response("Unauthorized", { status: 401 });
    const body = (await request.json()) as {
      sessionId: string;
      userId: string;
      outcome: string;
      score?: {
        concept: string;
        explanation: string;
        overallScore: number;
        scoresClear: number;
        scoresConcise: number;
        scoresConcrete: number;
        scoresCorrect: number;
        scoresCoherent: number;
        scoresComplete: number;
        scoresCourteous: number;
        criticism: string;
        summary: string;
      };
      refundAllowance: boolean;
    };
    try {
      const result = await ctx.runMutation(internal.feynman_internal.persistFeynman, body);
      return json(result);
    } catch (err) {
      return json({ error: (err as Error).message }, 404);
    }
  }),
});

export default http;
