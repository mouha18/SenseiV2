"use client";

import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";
import { ScopeTag } from "@/components/session/ScopeTag";
import { UploadZone } from "@/components/session/UploadZone";
import { ChatWindow } from "@/components/chat/ChatWindow";
import { ChatInput } from "@/components/chat/ChatInput";
import { TestMeButton } from "@/components/feynman/TestMeButton";

export default function SessionPage() {
  const params = useParams<{ id: string }>();
  const sessionId = params.id as Id<"sessions">;
  const router = useRouter();
  const session = useQuery(api.sessions.get, { sessionId });
  const documents = useQuery(api.documents.list, { sessionId });
  const [thinking, setThinking] = useState(false);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);

  function handleThinkingChange(next: boolean) {
    setThinking(next);
    if (!next) setPendingMessage(null);
  }

  if (session === undefined) return null;

  if (session === null) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="font-sans text-sm text-muted-foreground">Session not found.</p>
      </div>
    );
  }

  const isExpired = session.status === "expired";
  const isIngestInProgress = (documents ?? []).some((d) => d.status === "processing");

  return (
    <div className="flex h-screen flex-col">
      <div className="flex items-center justify-between gap-4 border-b border-border px-7 py-5">
        <div className="flex min-w-0 items-center gap-[18px]">
          <button
            onClick={() => router.push("/dashboard")}
            className="h-8 w-8 flex-none border border-border font-mono text-sm text-muted-foreground hover:border-muted-foreground hover:text-foreground"
          >
            ←
          </button>
          <ScopeTag session={session} />
        </div>
        <TestMeButton sessionId={sessionId} disabled={!session.scope} />
      </div>

      <UploadZone sessionId={sessionId} />

      <ChatWindow sessionId={sessionId} thinking={thinking} pendingMessage={pendingMessage} />

      {isExpired ? (
        <div className="border-t border-border px-8 py-4 text-center font-mono text-xs text-muted-foreground">
          This session has expired and is read-only. Start a new session to continue.
        </div>
      ) : (
        <ChatInput
          sessionId={sessionId}
          disabled={isIngestInProgress}
          onSendStart={setPendingMessage}
          onThinkingChange={handleThinkingChange}
        />
      )}
    </div>
  );
}
