import { getAuthUserId } from "@convex-dev/auth/server";
import { query } from "./_generated/server";
import { v } from "convex/values";

// Materials bar — live document status (processing/ready/failed/cancelled/
// rejected, ADR-0005). No create/update/cancel here: those stay FastAPI-only
// via the service-secret channel (ADR-0003/0010).
export const list = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, { sessionId }) => {
    const userId = await getAuthUserId(ctx);
    if (userId === null) return [];
    const session = await ctx.db.get(sessionId);
    if (session === null || session.userId !== userId) return [];
    return await ctx.db
      .query("documents")
      .withIndex("by_session", (q) => q.eq("sessionId", sessionId))
      .collect();
  },
});
