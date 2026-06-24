"use client";

import { useState } from "react";
import { useMutation } from "convex/react";
import { api } from "@/convex/_generated/api";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/Toast";

const TYPES = [
  { value: "bug", label: "Bug" },
  { value: "feedback", label: "Feedback" },
  { value: "idea", label: "Idea" },
] as const;

type FeedbackType = (typeof TYPES)[number]["value"];

export function FeedbackCard() {
  const [type, setType] = useState<FeedbackType>("feedback");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const submitFeedback = useMutation(api.feedback.submit);
  const { showToast } = useToast();

  async function handleSubmit() {
    if (!message.trim() || submitting) return;
    setSubmitting(true);
    try {
      await submitFeedback({ type, message: message.trim() });
      setMessage("");
      showToast("Feedback sent — thank you.");
    } catch {
      showToast("Failed to send feedback. Try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mt-14 border border-border bg-card px-[22px] py-5">
      <p className="font-sans text-[15px] font-medium text-foreground">
        Send feedback
      </p>
      <p className="mt-1 font-sans text-sm text-muted-foreground">
        Found a bug or have a suggestion? Let us know.
      </p>

      <div className="mt-4 flex gap-2">
        {TYPES.map((t) => (
          <button
            key={t.value}
            onClick={() => setType(t.value)}
            className={`border px-[9px] py-[5px] font-mono text-[10px] font-medium uppercase tracking-[.12em] transition-colors ${
              type === t.value
                ? "border-primary/40 text-primary"
                : "border-border text-muted-foreground/70 hover:border-muted-foreground hover:text-muted-foreground"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <Textarea
        className="mt-3 min-h-[88px] resize-none rounded-lg border border-input bg-transparent font-sans text-sm text-foreground placeholder:text-muted-foreground/50 focus-visible:ring-0"
        placeholder="Describe the issue or idea…"
        value={message}
        onChange={(e) => setMessage(e.target.value)}
      />

      <div className="mt-3 flex justify-end">
        <Button
          onClick={() => void handleSubmit()}
          disabled={!message.trim() || submitting}
          size="sm"
        >
          {submitting ? "Sending…" : "Send"}
        </Button>
      </div>
    </div>
  );
}
