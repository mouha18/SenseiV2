"use client";

import { useAuthToken } from "@convex-dev/auth/react";
import { useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { FeynmanResult } from "@/components/feynman/FeynmanResult";
import type { Id } from "@/convex/_generated/dataModel";

type Stage = "input" | "scoring" | "result";

export function FeynmanModal({
  sessionId,
  open,
  onOpenChange,
}: {
  sessionId: Id<"sessions">;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const token = useAuthToken();
  const [stage, setStage] = useState<Stage>("input");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [concept, setConcept] = useState("");
  const [explanation, setExplanation] = useState("");
  const [error, setError] = useState<string | null>(null);

  // No reset-on-open logic needed here: TestMeButton remounts this
  // component fresh (via `key`) every time it opens, so the useState
  // initializers above already start clean.
  useEffect(() => {
    if (!open) return;
    apiFetch<{ suggestions: string[] }>("/evaluate/suggestions", {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: JSON.stringify({ session_id: sessionId }),
    })
      .then((res) => setSuggestions(res.suggestions))
      .catch(() => setSuggestions([]));
  }, [open, sessionId, token]);

  async function handleSubmit() {
    if (!concept.trim() || !explanation.trim()) return;
    setError(null);
    setStage("scoring");
    try {
      await apiFetch("/evaluate/feynman", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: JSON.stringify({ session_id: sessionId, concept, explanation }),
      });
      setStage("result");
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Something went wrong. Please try again.",
      );
      setStage("input");
    }
  }

  function handleTryAgain() {
    setExplanation("");
    setStage("input");
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[88vh] max-w-[560px] gap-0 overflow-y-auto p-0">
        <div className="flex items-center justify-between border-b border-border px-[26px] py-5">
          <span className="font-mono text-[11px] font-medium uppercase tracking-[.16em] text-primary">
            ◇ Test me
          </span>
        </div>

        {stage === "input" && (
          <div className="px-[26px] py-[26px]">
            <h3 className="font-sans text-xl font-medium">Explain it back</h3>
            <p className="mt-1.5 font-sans text-[13px] leading-[1.6] text-muted-foreground">
              Pick a concept, then explain it as if teaching a beginner. Sensei
              scores you on the 7 C&apos;s.
            </p>

            <div className="mt-6 font-mono text-[10px] font-medium uppercase tracking-[.14em] text-muted-foreground/60">
              Concept
            </div>
            <div className="mt-[11px] flex flex-wrap gap-2">
              {suggestions.map((name) => (
                <button
                  key={name}
                  onClick={() => setConcept(name)}
                  className={`px-[13px] py-2 font-mono text-xs tracking-wide ${
                    concept === name
                      ? "border border-primary bg-primary text-primary-foreground"
                      : "border border-border text-muted-foreground hover:border-muted-foreground"
                  }`}
                >
                  {name}
                </button>
              ))}
            </div>
            <input
              value={concept}
              onChange={(e) => setConcept(e.target.value)}
              placeholder="Or type your own concept…"
              className="mt-3 w-full border border-border bg-transparent px-3 py-2 font-mono text-xs outline-none focus-visible:border-primary"
            />

            <div className="mt-6 font-mono text-[10px] font-medium uppercase tracking-[.14em] text-muted-foreground/60">
              Your explanation
            </div>
            <Textarea
              value={explanation}
              onChange={(e) => setExplanation(e.target.value)}
              rows={5}
              placeholder="In your own words…"
              className="mt-[11px] resize-y"
            />

            {error && <p className="mt-3 font-sans text-sm text-destructive">{error}</p>}

            <Button
              onClick={() => void handleSubmit()}
              disabled={!concept.trim() || !explanation.trim()}
              className="mt-5 w-full"
            >
              Evaluate explanation
            </Button>
          </div>
        )}

        {stage === "scoring" && (
          <div className="flex flex-col items-center gap-[22px] px-[26px] py-[60px]">
            <span className="inline-block h-[34px] w-[34px] animate-spin rounded-full border-2 border-border border-t-primary" />
            <span className="font-mono text-sm text-muted-foreground">
              Evaluating your explanation…
            </span>
            <span className="font-mono text-xs tracking-wide text-muted-foreground/50">
              clear · concise · concrete · correct · coherent · complete · courteous
            </span>
          </div>
        )}

        {stage === "result" && (
          <FeynmanResult
            sessionId={sessionId}
            concept={concept}
            onTryAgain={handleTryAgain}
            onClose={() => onOpenChange(false)}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
