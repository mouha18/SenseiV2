import type { Doc } from "@/convex/_generated/dataModel";

export function ScopeTag({ session }: { session: Doc<"sessions"> | null | undefined }) {
  if (session === undefined) return null;

  if (session === null || !session.scope) {
    return (
      <span className="font-mono text-xs text-muted-foreground/70">
        Scope not set yet — ask a question or upload a document
      </span>
    );
  }

  return (
    <div className="inline-flex min-w-0 items-center gap-2.5 border border-primary/40 px-3 py-[7px]">
      <span className="flex-none font-mono text-[10px] font-medium uppercase tracking-[.14em] text-primary">
        Scope
      </span>
      <span className="truncate font-mono text-[13px] text-foreground/90">
        {session.scope}
      </span>
      <span className="flex-none font-mono text-[11px] text-muted-foreground/60">
        locked
      </span>
    </div>
  );
}
