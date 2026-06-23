"use client";

import { useEffect, useState } from "react";

const CHARS_PER_TICK = 4;
const TICK_MS = 10;

// Each instance is mounted once per message (content is immutable once
// persisted, ADR-0010), so `text` never actually changes within an
// instance's lifetime — the initial 0 from useState is the only reset
// this needs; no synchronous setState-in-effect required.
export function TypewriterText({ text }: { text: string }) {
  const [shownLength, setShownLength] = useState(0);

  useEffect(() => {
    if (!text) return;
    const id = setInterval(() => {
      setShownLength((current) => {
        const next = current + CHARS_PER_TICK;
        if (next >= text.length) {
          clearInterval(id);
          return text.length;
        }
        return next;
      });
    }, TICK_MS);
    return () => clearInterval(id);
  }, [text]);

  return <>{text.slice(0, shownLength)}</>;
}
