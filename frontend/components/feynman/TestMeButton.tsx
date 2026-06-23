"use client";

import { useState } from "react";
import { FeynmanModal } from "@/components/feynman/FeynmanModal";
import type { Id } from "@/convex/_generated/dataModel";

export function TestMeButton({
  sessionId,
  disabled,
}: {
  sessionId: Id<"sessions">;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  // Bumped on every open so FeynmanModal remounts fresh (clean form state)
  // instead of resetting state from an effect.
  const [openKey, setOpenKey] = useState(0);

  function handleOpen() {
    setOpenKey((k) => k + 1);
    setOpen(true);
  }

  return (
    <>
      <button
        onClick={handleOpen}
        disabled={disabled}
        className="inline-flex flex-none items-center gap-2 whitespace-nowrap border border-primary/40 px-4 py-[9px] font-sans text-[13px] font-medium text-primary hover:border-primary hover:bg-primary/[0.06] disabled:opacity-40"
      >
        ◇ Test me
      </button>
      <FeynmanModal key={openKey} sessionId={sessionId} open={open} onOpenChange={setOpen} />
    </>
  );
}
