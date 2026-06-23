import Link from "next/link";
import type { Doc } from "@/convex/_generated/dataModel";

function formatRelative(timestamp: number): string {
  const diffMs = Date.now() - timestamp;
  const diffDays = Math.floor(diffMs / 86_400_000);
  if (diffDays <= 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return `${diffDays} days ago`;
}

export function SessionCard({ session }: { session: Doc<"sessions"> }) {
  const isExpired = session.status === "expired";

  return (
    <Link
      href={`/session/${session._id}`}
      className={`flex items-center justify-between gap-5 border border-border bg-card px-[22px] py-5 hover:border-muted-foreground ${
        isExpired ? "opacity-50" : ""
      }`}
    >
      <div className="flex min-w-0 flex-col gap-2">
        <span className="truncate font-sans text-[15px] font-medium text-foreground">
          {session.scope ?? "Untitled session"}
        </span>
        <span className="font-mono text-xs tracking-wide text-muted-foreground/70">
          {formatRelative(session.lastActivityAt)}
        </span>
      </div>
      <span
        className={`flex-none whitespace-nowrap border px-[9px] py-[5px] font-mono text-[10px] font-medium uppercase tracking-[.12em] ${
          isExpired
            ? "border-border text-muted-foreground/70"
            : "border-primary/40 text-primary"
        }`}
      >
        {isExpired ? "Expired" : "Active"}
      </span>
    </Link>
  );
}
