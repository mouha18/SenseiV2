import { getAuthUserId } from "@convex-dev/auth/server";
import { query } from "./_generated/server";
import { v } from "convex/values";

// FeynmanResult renders from this subscription, not just the raw POST
// response (ADR-0010) — scores are written server-side by FastAPI.
export const list = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, { sessionId }) => {
    const userId = await getAuthUserId(ctx);
    if (userId === null) return [];
    const session = await ctx.db.get(sessionId);
    if (session === null || session.userId !== userId) return [];
    const scores = await ctx.db
      .query("feynmanScores")
      .withIndex("by_session", (q) => q.eq("sessionId", sessionId))
      .collect();
    return scores.sort((a, b) => a.createdAt - b.createdAt);
  },
});
