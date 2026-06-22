import { internalMutation, internalQuery } from "./_generated/server";
import { v } from "convex/values";

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
