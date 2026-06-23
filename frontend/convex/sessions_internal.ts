import { internalAction, internalMutation, internalQuery } from "./_generated/server";
import { v } from "convex/values";
import { internal } from "./_generated/api";

const SESSION_EXPIRY_MS = 3 * 24 * 60 * 60 * 1000;

export const getIngestContext = internalQuery({
  args: { sessionId: v.string() },
  handler: async (ctx, { sessionId }) => {
    const id = ctx.db.normalizeId("sessions", sessionId);
    if (id === null) return null;
    const session = await ctx.db.get(id);
    if (session === null) return null;
    return {
      scope: session.scope ?? null,
      scopeDescription: session.scopeDescription ?? null,
      scopeSource: session.scopeSource ?? null,
      status: session.status,
      totalChunks: session.totalChunks,
      totalStorageBytes: session.totalStorageBytes,
    };
  },
});

// Scope locks exactly once, at the session's first interaction, and never
// moves again (ADR-0011) — re-locking is a programming error, not a retry.
export const lockSessionScope = internalMutation({
  args: {
    sessionId: v.string(),
    scope: v.string(),
    scopeDescription: v.optional(v.string()),
    scopeSource: v.string(),
  },
  handler: async (ctx, { sessionId, scope, scopeDescription, scopeSource }) => {
    const id = ctx.db.normalizeId("sessions", sessionId);
    if (id === null) throw new Error("Session not found");
    const session = await ctx.db.get(id);
    if (session === null) throw new Error("Session not found");
    if (session.scopeSource !== undefined) {
      throw new Error("Session scope is already locked");
    }
    await ctx.db.patch(id, { scope, scopeDescription, scopeSource, lastActivityAt: Date.now() });
  },
});

export const updateSessionTotals = internalMutation({
  args: {
    sessionId: v.string(),
    chunkDelta: v.number(),
    storageDelta: v.number(),
  },
  handler: async (ctx, { sessionId, chunkDelta, storageDelta }) => {
    const id = ctx.db.normalizeId("sessions", sessionId);
    if (id === null) throw new Error("Session not found");
    const session = await ctx.db.get(id);
    if (session === null) throw new Error("Session not found");
    await ctx.db.patch(id, {
      totalChunks: session.totalChunks + chunkDelta,
      totalStorageBytes: session.totalStorageBytes + storageDelta,
      lastActivityAt: Date.now(),
    });
  },
});

// ADR-0006: single clock (lastActivityAt), single hourly sweep.
export const listExpiryCandidates = internalQuery({
  args: {},
  handler: async (ctx) => {
    const cutoff = Date.now() - SESSION_EXPIRY_MS;
    const sessions = await ctx.db
      .query("sessions")
      .withIndex("by_status_activity", (q) => q.eq("status", "active").lt("lastActivityAt", cutoff))
      .collect();
    return sessions.map((session) => ({ sessionId: session._id, userId: session.userId }));
  },
});

export const markSessionExpired = internalMutation({
  args: { sessionId: v.string() },
  handler: async (ctx, { sessionId }) => {
    const id = ctx.db.normalizeId("sessions", sessionId);
    if (id === null) throw new Error("Session not found");
    await ctx.db.patch(id, { status: "expired" });
  },
});

// Hourly cron entry point (convex/crons.ts). A single session's cleanup
// failure must not abort the batch — it just stays "active" for the next
// run to retry (ADR-0006's retry-safe consistency).
export const cleanupExpiredSessions = internalAction({
  args: {},
  handler: async (ctx) => {
    const candidates = await ctx.runQuery(internal.sessions_internal.listExpiryCandidates, {});
    const fastApiUrl = process.env.FASTAPI_URL ?? "";
    const serviceSecret = process.env.CONVEX_SERVICE_SECRET ?? "";

    for (const { sessionId, userId } of candidates) {
      try {
        const storagePaths = await ctx.runQuery(internal.documents_internal.getStoragePaths, {
          sessionId,
        });
        const response = await fetch(`${fastApiUrl}/internal/cleanupSession`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Service-Secret": serviceSecret,
          },
          body: JSON.stringify({ session_id: sessionId, user_id: userId, storage_paths: storagePaths }),
        });
        if (!response.ok) {
          console.error(`cleanupSession failed for ${sessionId}: ${response.status}`);
          continue;
        }
        await ctx.runMutation(internal.sessions_internal.markSessionExpired, { sessionId });
      } catch (err) {
        console.error(`cleanupSession threw for ${sessionId}:`, err);
      }
    }
  },
});
