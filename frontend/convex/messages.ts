import { getAuthUserId } from "@convex-dev/auth/server";
import { query } from "./_generated/server";
import { v } from "convex/values";

// Chat history for ChatWindow — ownership-checked via the parent session,
// since messages are written server-side by FastAPI (ADR-0010), never the
// client. Oldest -> newest for direct rendering.
export const list = query({
  args: { sessionId: v.id("sessions") },
  handler: async (ctx, { sessionId }) => {
    const userId = await getAuthUserId(ctx);
    if (userId === null) return [];
    const session = await ctx.db.get(sessionId);
    if (session === null || session.userId !== userId) return [];
    const messages = await ctx.db
      .query("messages")
      .withIndex("by_session", (q) => q.eq("sessionId", sessionId))
      .collect();
    return messages.sort((a, b) => a.createdAt - b.createdAt);
  },
});
