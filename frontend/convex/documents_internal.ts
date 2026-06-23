import { internalMutation, internalQuery } from "./_generated/server";
import { v } from "convex/values";

export const createDocument = internalMutation({
  args: {
    sessionId: v.string(),
    userId: v.string(),
    fileName: v.string(),
    fileSizeBytes: v.number(),
    storagePath: v.string(),
  },
  handler: async (ctx, { sessionId, userId, fileName, fileSizeBytes, storagePath }) => {
    const sessionDocId = ctx.db.normalizeId("sessions", sessionId);
    const userDocId = ctx.db.normalizeId("users", userId);
    if (sessionDocId === null) throw new Error("Session not found");
    if (userDocId === null) throw new Error("User not found");
    return await ctx.db.insert("documents", {
      sessionId: sessionDocId,
      userId: userDocId,
      fileName,
      fileSizeBytes,
      status: "processing",
      chunkCount: 0,
      storagePath,
      createdAt: Date.now(),
    });
  },
});

export const updateDocumentStatus = internalMutation({
  args: {
    documentId: v.string(),
    status: v.string(),
    chunkCount: v.optional(v.number()),
    error: v.optional(v.string()),
  },
  handler: async (ctx, { documentId, status, chunkCount, error }) => {
    const id = ctx.db.normalizeId("documents", documentId);
    if (id === null) throw new Error("Document not found");
    await ctx.db.patch(id, {
      status,
      ...(chunkCount !== undefined ? { chunkCount } : {}),
      ...(error !== undefined ? { error } : {}),
    });
  },
});

export const getDocument = internalQuery({
  args: { documentId: v.string() },
  handler: async (ctx, { documentId }) => {
    const id = ctx.db.normalizeId("documents", documentId);
    if (id === null) return null;
    return await ctx.db.get(id);
  },
});

// ADR-0006: FastAPI's cleanup endpoint only knows the session id, so the
// cron hands it every document's storage path up front (FastAPI has no
// direct Convex read access — ADR-0003/0010).
export const getStoragePaths = internalQuery({
  args: { sessionId: v.string() },
  handler: async (ctx, { sessionId }) => {
    const id = ctx.db.normalizeId("sessions", sessionId);
    if (id === null) return [];
    const documents = await ctx.db
      .query("documents")
      .withIndex("by_session", (q) => q.eq("sessionId", id))
      .collect();
    return documents.map((doc) => doc.storagePath);
  },
});
