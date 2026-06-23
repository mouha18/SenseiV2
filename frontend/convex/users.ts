import { getAuthUserId } from "@convex-dev/auth/server";
import { mutation, query } from "./_generated/server";
import { v } from "convex/values";

export const getMe = query({
  args: {},
  handler: async (ctx) => {
    const userId = await getAuthUserId(ctx);
    if (userId === null) return null;
    const user = await ctx.db.get(userId);
    if (user === null) return null;
    return {
      email: user.email,
      hasGeminiKey: user.geminiApiKey !== undefined,
      onboardedAt: user.onboardedAt ?? null,
    };
  },
});

// Onboarding tour (PRD open items: Shepherd.js, shown once, not replayable
// for MVP) — called on tour completion or skip.
export const markOnboarded = mutation({
  args: {},
  handler: async (ctx) => {
    const userId = await getAuthUserId(ctx);
    if (userId === null) throw new Error("Not authenticated");
    await ctx.db.patch(userId, { onboardedAt: Date.now() });
  },
});

export const setGeminiKey = mutation({
  args: { ciphertext: v.string() },
  handler: async (ctx, { ciphertext }) => {
    const userId = await getAuthUserId(ctx);
    if (userId === null) throw new Error("Not authenticated");
    await ctx.db.patch(userId, { geminiApiKey: ciphertext });
  },
});

export const clearGeminiKey = mutation({
  args: {},
  handler: async (ctx) => {
    const userId = await getAuthUserId(ctx);
    if (userId === null) throw new Error("Not authenticated");
    await ctx.db.patch(userId, { geminiApiKey: undefined });
  },
});

export const revokeSessions = mutation({
  args: {},
  handler: async (ctx) => {
    const userId = await getAuthUserId(ctx);
    if (userId === null) throw new Error("Not authenticated");
    await ctx.db.patch(userId, { tokensValidAfter: Date.now() });
  },
});
