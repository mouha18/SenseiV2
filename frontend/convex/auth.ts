import { Password } from "@convex-dev/auth/providers/Password";
import { convexAuth } from "@convex-dev/auth/server";

function nextUtcMidnight(): number {
  const now = new Date();
  const next = new Date(
    Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1),
  );
  return next.getTime();
}

export const { auth, signIn, signOut, store, isAuthenticated } = convexAuth({
  providers: [Password],
  callbacks: {
    async afterUserCreatedOrUpdated(ctx, args) {
      if (args.existingUserId) return;
      await ctx.db.patch(args.userId, {
        dailyDefaultKeyCount: 0,
        dailyCountResetAt: nextUtcMidnight(),
        velocityCount: 0,
        velocityWindowStart: 0,
        tokensValidAfter: 0,
        createdAt: Date.now(),
      });
    },
  },
});
