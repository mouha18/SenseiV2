import { internalMutation } from "./_generated/server";
import { v } from "convex/values";

// The Feynman analogue of persistTurn (ADR-0010 extension): writes the score
// atomically, refunding the allowance on a failed eval. attemptNumber is
// computed here (not passed by FastAPI) to avoid a client/FastAPI race.
export const persistFeynman = internalMutation({
  args: {
    sessionId: v.string(),
    userId: v.string(),
    outcome: v.string(),
    score: v.optional(
      v.object({
        concept: v.string(),
        explanation: v.string(),
        overallScore: v.number(),
        scoresClear: v.number(),
        scoresConcise: v.number(),
        scoresConcrete: v.number(),
        scoresCorrect: v.number(),
        scoresCoherent: v.number(),
        scoresComplete: v.number(),
        scoresCourteous: v.number(),
        criticism: v.string(),
        summary: v.string(),
      }),
    ),
    refundAllowance: v.boolean(),
  },
  handler: async (ctx, { sessionId, userId, outcome, score, refundAllowance }) => {
    const sessionDocId = ctx.db.normalizeId("sessions", sessionId);
    const userDocId = ctx.db.normalizeId("users", userId);
    if (sessionDocId === null) throw new Error("Session not found");
    if (userDocId === null) throw new Error("User not found");

    const now = Date.now();
    let scoreId = null;
    let attemptNumber = null;

    if (outcome === "scored") {
      if (score === undefined) throw new Error("score is required when outcome is 'scored'");
      const existingAttempts = await ctx.db
        .query("feynmanScores")
        .withIndex("by_session", (q) => q.eq("sessionId", sessionDocId))
        .collect();
      attemptNumber =
        existingAttempts.filter((a) => a.concept === score.concept).length + 1;

      scoreId = await ctx.db.insert("feynmanScores", {
        sessionId: sessionDocId,
        userId: userDocId,
        concept: score.concept,
        explanation: score.explanation,
        overallScore: score.overallScore,
        scoresClear: score.scoresClear,
        scoresConcise: score.scoresConcise,
        scoresConcrete: score.scoresConcrete,
        scoresCorrect: score.scoresCorrect,
        scoresCoherent: score.scoresCoherent,
        scoresComplete: score.scoresComplete,
        scoresCourteous: score.scoresCourteous,
        criticism: score.criticism,
        summary: score.summary,
        attemptNumber,
        createdAt: now,
      });
    }

    await ctx.db.patch(sessionDocId, { lastActivityAt: now });

    if (refundAllowance) {
      const user = await ctx.db.get(userDocId);
      if (user !== null) {
        const current = user.dailyDefaultKeyCount ?? 0;
        await ctx.db.patch(userDocId, { dailyDefaultKeyCount: Math.max(0, current - 1) });
      }
    }

    return { scoreId, attemptNumber };
  },
});
