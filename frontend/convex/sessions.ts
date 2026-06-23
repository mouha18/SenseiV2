import { getAuthUserId } from "@convex-dev/auth/server";
import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

// No session-creation path exists anywhere yet (Sprint 6 builds the dashboard
// UI on top of this). Minimal public mutation so a session can exist at all
// for ingestion/chat to target.
export const createSession = mutation({
  args: {},
  handler: async (ctx) => {
    const userId = await getAuthUserId(ctx);
    if (userId === null) throw new Error("Not authenticated");
    const now = Date.now();
    return await ctx.db.insert("sessions", {
      userId,
      status: "active",
      outOfScopeCount: 0,
      totalChunks: 0,
      totalStorageBytes: 0,
      lastActivityAt: now,
      createdAt: now,
    });
  },
});

// Dashboard session list — newest first, current user only.
export const list = query({
  args: {},
  handler: async (ctx) => {
    const userId = await getAuthUserId(ctx);
    if (userId === null) return [];
    return await ctx.db
      .query("sessions")
      .withIndex("by_user", (q) => q.eq("userId", userId))
      .order("desc")
      .collect();
  },
});

// Single session, ownership-checked — powers ScopeTag and the session page.
export const get = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, { sessionId }) => {
    const userId = await getAuthUserId(ctx);
    if (userId === null) return null;
    const session = await ctx.db.get(sessionId);
    if (session === null || session.userId !== userId) return null;
    return session;
  },
});
