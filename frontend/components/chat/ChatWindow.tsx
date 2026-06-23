"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import type { Id } from "@/convex/_generated/dataModel";
import { TypewriterText } from "@/components/chat/TypewriterText";

const TAG_MAP: Record<string, { label: string; color: string }> = {
  socratic: { label: "[socratic]", color: "text-primary" },
  direct: { label: "[direct]", color: "text-primary" },
  redirect: { label: "[off-topic]", color: "text-destructive" },
  new_session_prompt: { label: "[new session?]", color: "text-destructive" },
};

function AssistantMessage({
  content,
  responseType,
  isHistorical,
}: {
  content: string;
  responseType: string | null;
  isHistorical: boolean;
}) {
  // Decided once, on mount, from the snapshot the message first appeared
  // in — never re-evaluated, so the animation can't be cut short by a
  // later re-render reclassifying this message as "no longer new".
  const [shouldAnimate] = useState(() => !isHistorical);
  const tag = responseType ? TAG_MAP[responseType] : undefined;

  return (
    <div className="max-w-[90%] whitespace-pre-wrap font-mono text-[15px] leading-[1.7] text-foreground/90">
      {tag && <span className={`mr-1 ${tag.color}`}>{tag.label}</span>}
      {shouldAnimate ? <TypewriterText text={content} /> : content}
    </div>
  );
}

type Message = {
  _id: string;
  role: string;
  content: string;
  responseType?: string | null;
};

// Only mounts once `messages` is loaded for the first time — its lazy
// useState initializer then captures that first snapshot's ids exactly
// once, with no ref-during-render or setState-in-effect involved.
function ChatMessages({
  messages,
  thinking,
  pendingMessage,
}: {
  messages: Message[];
  thinking: boolean;
  pendingMessage?: string | null;
}) {
  const [initialIds] = useState(() => new Set(messages.map((m) => m._id)));
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: "end" });
  }, [messages, thinking, pendingMessage]);

  return (
    <div className="flex-1 overflow-y-auto pt-12 pb-8">
      <div className="mx-auto flex max-w-[720px] flex-col gap-7 px-8">
        {messages.map((message) => {
          if (message.role === "user") {
            return (
              <div key={message._id} className="flex justify-end">
                <div className="max-w-[82%] border border-secondary bg-secondary px-[15px] py-3 font-sans text-[15px] leading-[1.55] text-foreground">
                  {message.content}
                </div>
              </div>
            );
          }
          return (
            <AssistantMessage
              key={message._id}
              content={message.content}
              responseType={message.responseType ?? null}
              isHistorical={initialIds.has(message._id)}
            />
          );
        })}

        {pendingMessage && (
          <div className="flex justify-end">
            <div className="max-w-[82%] border border-secondary bg-secondary px-[15px] py-3 font-sans text-[15px] leading-[1.55] text-foreground">
              {pendingMessage}
            </div>
          </div>
        )}

        {thinking && (
          <div className="flex items-center gap-[5px]">
            <span className="h-1.5 w-1.5 animate-pulse bg-muted-foreground/60" />
            <span className="h-1.5 w-1.5 animate-pulse bg-muted-foreground/60 [animation-delay:0.2s]" />
            <span className="h-1.5 w-1.5 animate-pulse bg-muted-foreground/60 [animation-delay:0.4s]" />
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}

export function ChatWindow({
  sessionId,
  thinking,
  pendingMessage,
}: {
  sessionId: Id<"sessions">;
  thinking: boolean;
  pendingMessage?: string | null;
}) {
  const messages = useQuery(api.messages.list, { sessionId });
  if (messages === undefined) return <div className="flex-1" />;
  return (
    <ChatMessages messages={messages} thinking={thinking} pendingMessage={pendingMessage} />
  );
}
