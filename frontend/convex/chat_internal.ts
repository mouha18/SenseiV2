import { internalMutation } from "./_generated/server";
import { v } from "convex/values";

const VELOCITY_WINDOW_MS = 60_000;
const VELOCITY_LIMIT = 20;
const ALLOWANCE_LIMIT = 20;

function nextUtcMidnight(): number {
  const now = new Date();
  const next = new Date(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1),
  );
  return next.getTime();
}

// The per-request start call (ADR-0010): velocity gate + everything FastAPI
// needs to handle a /chat/ask request, in one round-trip. Returns tagged
// results rather than throwing for expected outcomes (rate-limited, expired,
// ingest-in-progress) — only a genuinely missing session/user is an error.
export const getRequestContext = internalMutation({
  args: {
    userId: v.string(),
    sessionId: v.string(),
    recentMessageLimit: v.number(),
  },
  handler: async (ctx, { userId, sessionId, recentMessageLimit }) => {
    const userDocId = ctx.db.normalizeId("users", userId);
    const sessionDocId = ctx.db.normalizeId("sessions", sessionId);
    if (userDocId === null) throw new Error("User not found");
    if (sessionDocId === null) throw new Error("Session not found");

    const user = await ctx.db.get(userDocId);
    const session = await ctx.db.get(sessionDocId);
    if (user === null) throw new Error("User not found");
    if (session === null) throw new Error("Session not found");
    if (session.userId !== userDocId) throw new Error("Session not found");

    // Velocity — fixed 60s window, checked-and-consumed first (ADR-0001).
    // Not restamped on in-window requests, or the window slides forever.
    const now = Date.now();
    const windowStart = user.velocityWindowStart ?? 0;
    const windowCount = user.velocityCount ?? 0;
    let newVelocityCount: number;
    let newVelocityWindowStart: number;
    if (now - windowStart >= VELOCITY_WINDOW_MS) {
      newVelocityWindowStart = now;
      newVelocityCount = 1;
    } else if (windowCount >= VELOCITY_LIMIT) {
      return {
        rateLimited: true as const,
        resetsInMs: windowStart + VELOCITY_WINDOW_MS - now,
      };
    } else {
      newVelocityWindowStart = windowStart;
      newVelocityCount = windowCount + 1;
    }
    await ctx.db.patch(userDocId, {
      velocityCount: newVelocityCount,
      velocityWindowStart: newVelocityWindowStart,
    });

    if (session.status === "expired") {
      return { rateLimited: false as const, sessionExpired: true as const };
    }

    const processingDocs = await ctx.db
      .query("documents")
      .withIndex("by_session", (q) => q.eq("sessionId", sessionDocId))
      .collect();
    const ingestInProgress = processingDocs.some((d) => d.status === "processing");
    if (ingestInProgress) {
      return {
        rateLimited: false as const,
        sessionExpired: false as const,
        ingestInProgress: true as const,
      };
    }

    const recentMessages = await ctx.db
      .query("messages")
      .withIndex("by_session", (q) => q.eq("sessionId", sessionDocId))
      .order("desc")
      .take(recentMessageLimit);
    recentMessages.reverse();

    return {
      rateLimited: false as const,
      sessionExpired: false as const,
      ingestInProgress: false as const,
      keyCiphertext: user.geminiApiKey ?? null,
      session: {
        scope: session.scope ?? null,
        scopeDescription: session.scopeDescription ?? null,
        scopeSource: session.scopeSource ?? null,
        outOfScopeCount: session.outOfScopeCount,
        totalChunks: session.totalChunks,
      },
      recentMessages: recentMessages.map((m) => ({
        role: m.role,
        content: m.content,
        responseType: m.responseType ?? null,
        source: m.source ?? null,
      })),
    };
  },
});

// Post-scope, Default-Key-only check-and-increment (ADR-0001).
export const consumeAllowance = internalMutation({
  args: { userId: v.string() },
  handler: async (ctx, { userId }) => {
    const userDocId = ctx.db.normalizeId("users", userId);
    if (userDocId === null) throw new Error("User not found");
    const user = await ctx.db.get(userDocId);
    if (user === null) throw new Error("User not found");

    const now = Date.now();
    let count = user.dailyDefaultKeyCount ?? 0;
    let resetsAt = user.dailyCountResetAt ?? 0;
    if (now >= resetsAt) {
      count = 0;
      resetsAt = nextUtcMidnight();
    }

    if (count >= ALLOWANCE_LIMIT) {
      await ctx.db.patch(userDocId, { dailyCountResetAt: resetsAt });
      return { allowed: false as const, resetsAt };
    }

    const newCount = count + 1;
    await ctx.db.patch(userDocId, {
      dailyDefaultKeyCount: newCount,
      dailyCountResetAt: resetsAt,
    });
    return { allowed: true as const, count: newCount, resetsAt };
  },
});

// Atomic chat-turn write (ADR-0010): user + assistant message, the
// out-of-scope counter, lastActivityAt, and an allowance refund on failure.
// `userMessage` is optional so FastAPI can also persist a proactive,
// assistant-only "greeting" turn (e.g. the opening question right after a
// document-first upload locks scope) with no preceding student message.
export const persistTurn = internalMutation({
  args: {
    sessionId: v.string(),
    userId: v.string(),
    userMessage: v.optional(v.object({ content: v.string() })),
    outcome: v.string(),
    assistantMessage: v.optional(
      v.object({
        content: v.string(),
        responseType: v.string(),
        source: v.optional(v.string()),
      }),
    ),
    refundAllowance: v.boolean(),
  },
  handler: async (ctx, { sessionId, userId, userMessage, outcome, assistantMessage, refundAllowance }) => {
    const sessionDocId = ctx.db.normalizeId("sessions", sessionId);
    const userDocId = ctx.db.normalizeId("users", userId);
    if (sessionDocId === null) throw new Error("Session not found");
    if (userDocId === null) throw new Error("User not found");

    const now = Date.now();
    const messageIds = [];

    if (userMessage !== undefined) {
      messageIds.push(
        await ctx.db.insert("messages", {
          sessionId: sessionDocId,
          userId: userDocId,
          role: "user",
          content: userMessage.content,
          createdAt: now,
        }),
      );
    }

    if (assistantMessage !== undefined) {
      messageIds.push(
        await ctx.db.insert("messages", {
          sessionId: sessionDocId,
          userId: userDocId,
          role: "assistant",
          content: assistantMessage.content,
          responseType: assistantMessage.responseType,
          source: assistantMessage.source,
          createdAt: now,
        }),
      );
    }

    const session = await ctx.db.get(sessionDocId);
    if (session === null) throw new Error("Session not found");
    const outOfScopeCount =
      outcome === "redirect" || outcome === "new_session_prompt" ? session.outOfScopeCount + 1 : 0;
    await ctx.db.patch(sessionDocId, { outOfScopeCount, lastActivityAt: now });

    if (refundAllowance) {
      const user = await ctx.db.get(userDocId);
      if (user !== null) {
        const current = user.dailyDefaultKeyCount ?? 0;
        await ctx.db.patch(userDocId, { dailyDefaultKeyCount: Math.max(0, current - 1) });
      }
    }

    return { messageIds, outOfScopeCount };
  },
});
