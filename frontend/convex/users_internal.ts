import { internalQuery } from "./_generated/server";
import { v } from "convex/values";

export const getTokensValidAfter = internalQuery({
  args: { userId: v.string() },
  handler: async (ctx, { userId }) => {
    const id = ctx.db.normalizeId("users", userId);
    if (id === null) return null;
    const user = await ctx.db.get(id);
    if (user === null) return null;
    return user.tokensValidAfter ?? 0;
  },
});
