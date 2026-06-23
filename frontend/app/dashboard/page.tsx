"use client";

import { useMutation, useQuery } from "convex/react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/convex/_generated/api";
import { Button } from "@/components/ui/button";
import { SessionCard } from "@/components/dashboard/SessionCard";
import { OnboardingTour } from "@/components/ui/OnboardingTour";

export default function DashboardPage() {
  const sessions = useQuery(api.sessions.list);
  const createSession = useMutation(api.sessions.createSession);
  const router = useRouter();
  const [creating, setCreating] = useState(false);

  // Warms the /session/[id] route bundle ahead of the click — in dev mode
  // the first visit to an unvisited route compiles on demand, which is
  // most of what made "+ New session" feel like it hung for several
  // seconds.
  useEffect(() => {
    router.prefetch("/session/placeholder");
  }, [router]);

  async function handleNewSession() {
    if (creating) return;
    setCreating(true);
    const sessionId = await createSession({});
    router.push(`/session/${sessionId}`);
  }

  if (sessions === undefined) return null;

  return (
    <div className="min-h-screen">
      <OnboardingTour />
      <header className="flex items-center justify-between border-b border-border px-10 py-6">
        <div className="flex items-center gap-2.5">
          <span className="inline-block h-[11px] w-[11px] bg-primary" />
          <span className="font-sans text-base font-semibold">Sensei</span>
        </div>
        <Link
          href="/settings"
          className="font-sans text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          Settings
        </Link>
      </header>

      <main className="mx-auto max-w-[880px] px-10 py-14">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-sans text-[30px] font-medium tracking-[-.015em]">
              Sessions
            </h1>
            <p className="mt-2 font-sans text-sm text-muted-foreground">
              Each session locks to one topic and expires after 3 days of
              inactivity.
            </p>
          </div>
          <Button
            id="dashboard-new-session"
            onClick={() => void handleNewSession()}
            disabled={creating}
            className="whitespace-nowrap"
          >
            {creating ? "Creating…" : "+ New session"}
          </Button>
        </div>

        {sessions.length === 0 ? (
          <div className="border border-dashed border-border px-6 py-14 text-center font-sans text-sm text-muted-foreground">
            No sessions yet — start one to begin studying.
          </div>
        ) : (
          <div id="dashboard-session-list" className="flex flex-col gap-2.5">
            {sessions.map((session) => (
              <SessionCard key={session._id} session={session} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
