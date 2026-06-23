"use client";

import { useState } from "react";
import { useQuery } from "convex/react";
import { api } from "@/convex/_generated/api";
import { Button } from "@/components/ui/button";
import type { Id } from "@/convex/_generated/dataModel";
import type { FeynmanCriticism } from "@/lib/api";

export function FeynmanResult({
  sessionId,
  concept,
  onTryAgain,
  onClose,
}: {
  sessionId: Id<"sessions">;
  concept: string;
  onTryAgain: () => void;
  onClose: () => void;
}) {
  const [detailOpen, setDetailOpen] = useState(false);
  const scores = useQuery(api.feynmanScores.list, { sessionId });

  const conceptScores = scores?.filter((s) => s.concept === concept);
  const score =
    conceptScores && conceptScores.length > 0
      ? conceptScores[conceptScores.length - 1]
      : undefined;

  if (score === undefined) {
    return (
      <div className="px-[26px] py-[60px] text-center font-mono text-sm text-muted-foreground">
        Loading score…
      </div>
    );
  }

  const criticism = JSON.parse(score.criticism) as FeynmanCriticism;
  const verdict = score.overallScore >= 70 ? "Passing" : "Needs another pass";
  const rows: { label: string; value: number; note: string }[] = [
    { label: "Clear", value: score.scoresClear, note: criticism.clear },
    { label: "Concise", value: score.scoresConcise, note: criticism.concise },
    { label: "Concrete", value: score.scoresConcrete, note: criticism.concrete },
    { label: "Correct", value: score.scoresCorrect, note: criticism.correct },
    { label: "Coherent", value: score.scoresCoherent, note: criticism.coherent },
    { label: "Complete", value: score.scoresComplete, note: criticism.complete },
  ];

  return (
    <div className="px-[26px] py-[26px]">
      <div className="font-mono text-[10px] font-medium uppercase tracking-[.14em] text-muted-foreground/60">
        {score.concept}
      </div>
      <div className="mt-2.5 flex items-baseline gap-3.5">
        <span className="font-mono text-[54px] font-medium leading-none text-primary">
          {score.overallScore}
        </span>
        <span className="font-sans text-[13px] text-muted-foreground">
          / 100 · {verdict}
        </span>
      </div>
      <p className="mt-[18px] font-mono text-[15px] leading-[1.65] text-foreground/90">
        {score.summary}
      </p>

      <button
        onClick={() => setDetailOpen((v) => !v)}
        className="mt-5 font-mono text-xs font-medium tracking-wide text-primary"
      >
        {detailOpen ? "Hide 7C breakdown ↑" : "View 7C breakdown ↓"}
      </button>

      {detailOpen && (
        <div className="mt-[22px] flex flex-col gap-4 border-t border-border pt-[22px]">
          {rows.map((row) => {
            const low = row.value < 70;
            return (
              <div key={row.label} className="flex flex-col gap-1.5">
                <div className="flex items-baseline justify-between">
                  <span className="font-mono text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                    {row.label}
                  </span>
                  <span
                    className={`font-mono text-xs font-medium ${low ? "text-destructive" : "text-primary"}`}
                  >
                    {row.value}
                  </span>
                </div>
                <div className="h-0.5 bg-border">
                  <div
                    className={`h-0.5 ${low ? "bg-destructive" : "bg-primary"}`}
                    style={{ width: `${row.value}%` }}
                  />
                </div>
                <span className="font-sans text-xs leading-[1.5] text-muted-foreground/80">
                  {row.note}
                </span>
              </div>
            );
          })}
          <div className="flex flex-col gap-1.5 opacity-70">
            <div className="flex items-baseline justify-between">
              <span className="font-mono text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
                Courteous
              </span>
              <span className="font-mono text-xs font-medium text-primary">
                {score.scoresCourteous}
              </span>
            </div>
            <span className="font-sans text-xs leading-[1.5] text-muted-foreground/80">
              Not counted toward the overall score.
            </span>
          </div>
        </div>
      )}

      <div className="mt-[26px] flex gap-2.5">
        <Button variant="outline" onClick={onTryAgain} className="flex-1">
          Try again
        </Button>
        <Button onClick={onClose} className="flex-1">
          Continue
        </Button>
      </div>
    </div>
  );
}
