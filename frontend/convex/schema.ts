import { defineSchema, defineTable } from "convex/server";
import { v } from "convex/values";
import { authTables } from "@convex-dev/auth/server";

export default defineSchema({
  ...authTables,

  // Extends Convex Auth's default `users` table (authTables.users) with our
  // app-specific fields. These are optional in the schema because Convex
  // Auth's internal account-creation insert doesn't set them — our
  // `afterUserCreatedOrUpdated` callback (convex/auth.ts) patches them in
  // immediately after, within the same mutation.
  users: defineTable({
    email: v.string(),
    geminiApiKey: v.optional(v.string()),
    dailyDefaultKeyCount: v.optional(v.number()),
    dailyCountResetAt: v.optional(v.number()),
    velocityCount: v.optional(v.number()),
    velocityWindowStart: v.optional(v.number()),
    tokensValidAfter: v.optional(v.number()),
    onboardedAt: v.optional(v.number()),
    createdAt: v.optional(v.number()),
  }).index("email", ["email"]),

  sessions: defineTable({
    userId: v.id("users"),
    scope: v.optional(v.string()),
    scopeDescription: v.optional(v.string()),
    scopeSource: v.optional(v.string()),
    status: v.string(),
    outOfScopeCount: v.number(),
    totalChunks: v.number(),
    totalStorageBytes: v.number(),
    lastActivityAt: v.number(),
    createdAt: v.number(),
  })
    .index("by_user", ["userId"])
    .index("by_status_activity", ["status", "lastActivityAt"]),

  messages: defineTable({
    sessionId: v.id("sessions"),
    userId: v.id("users"),
    role: v.string(),
    content: v.string(),
    responseType: v.optional(v.string()),
    source: v.optional(v.string()),
    createdAt: v.number(),
  }).index("by_session", ["sessionId"]),

  feynmanScores: defineTable({
    sessionId: v.id("sessions"),
    userId: v.id("users"),
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
    attemptNumber: v.number(),
    createdAt: v.number(),
  }).index("by_session", ["sessionId"]),

  documents: defineTable({
    sessionId: v.id("sessions"),
    userId: v.id("users"),
    fileName: v.string(),
    fileSizeBytes: v.number(),
    status: v.string(),
    chunkCount: v.number(),
    storagePath: v.string(),
    error: v.optional(v.string()),
    createdAt: v.number(),
  }).index("by_session", ["sessionId"]),
});
