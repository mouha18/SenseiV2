"use client";

import { useAuthToken } from "@convex-dev/auth/react";
import { useState, type KeyboardEvent } from "react";
import { apiFetch, ApiError, type ChatResponse } from "@/lib/api";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/Toast";
import type { Id } from "@/convex/_generated/dataModel";

export function ChatInput({
  sessionId,
  disabled,
  onSendStart,
  onThinkingChange,
}: {
  sessionId: Id<"sessions">;
  disabled?: boolean;
  onSendStart: (question: string) => void;
  onThinkingChange: (thinking: boolean) => void;
}) {
  const token = useAuthToken();
  const { showToast } = useToast();
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);

  async function send() {
    const question = draft.trim();
    if (!question || sending) return;
    setDraft("");
    setSending(true);
    // Renders the user's own message immediately, before the round trip —
    // otherwise both it and the answer only appear together once
    // persistTurn writes them, since they're written atomically at the
    // end of the pipeline (ADR-0010).
    onSendStart(question);
    onThinkingChange(true);
    try {
      // The real message list is purely Convex-subscription-driven
      // (ADR-0010) — persistTurn already wrote both rows by the time this
      // resolves, so there's nothing to do with the response here.
      await apiFetch<ChatResponse>("/chat/ask", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({ session_id: sessionId, question }),
      });
    } catch (err) {
      showToast(
        err instanceof ApiError ? err.message : "Something went wrong. Please try again.",
      );
    } finally {
      setSending(false);
      onThinkingChange(false);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send();
    }
  }

  return (
    <div className="border-t border-border py-4">
      <div className="mx-auto flex max-w-[720px] items-end gap-2.5 px-8">
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          rows={1}
          placeholder="Ask a question…"
          disabled={disabled || sending}
          className="max-h-[140px] min-h-[48px] flex-1 resize-none"
        />
        <Button
          onClick={() => void send()}
          disabled={disabled || sending}
          className="h-[48px] px-[22px]"
        >
          Send
        </Button>
      </div>
      <div className="mx-auto mt-2 max-w-[720px] px-8 font-mono text-[11px] text-muted-foreground/50">
        Enter to send · Shift+Enter for newline
      </div>
    </div>
  );
}
