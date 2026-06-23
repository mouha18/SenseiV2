import { v } from "convex/values";
import { mutation } from "./_generated/server";
import { getAuthUserId } from "@convex-dev/auth/server";

export const submit = mutation({
  args: { type: v.string(), message: v.string() },
  handler: async (ctx, { type, message }) => {
    const userId = await getAuthUserId(ctx);
    if (!userId) throw new Error("Not authenticated");
    await ctx.db.insert("feedback", {
      userId,
      type,
      message,
      createdAt: Date.now(),
    });
  },
});
