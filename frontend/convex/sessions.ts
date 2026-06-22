import { getAuthUserId } from "@convex-dev/auth/server";
import { mutation } from "./_generated/server";

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
