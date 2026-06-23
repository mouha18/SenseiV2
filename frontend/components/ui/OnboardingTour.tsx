"use client";

import { useEffect } from "react";
import { useMutation, useQuery } from "convex/react";
import Shepherd from "shepherd.js";
import "shepherd.js/dist/css/shepherd.css";
import { api } from "@/convex/_generated/api";

// PRD open items: Shepherd.js, shown once on first login (users.onboardedAt),
// non-blocking and skippable, not replayable for MVP.
export function OnboardingTour() {
  const me = useQuery(api.users.getMe);
  const markOnboarded = useMutation(api.users.markOnboarded);

  useEffect(() => {
    if (me === undefined || me === null || me.onboardedAt !== null) return;

    const tour = new Shepherd.Tour({
      useModalOverlay: true,
      exitOnEsc: true,
      defaultStepOptions: {
        classes: "sensei-tour-step",
        scrollTo: false,
        cancelIcon: { enabled: true },
      },
    });

    function finish() {
      void markOnboarded({});
    }
    tour.on("complete", finish);
    tour.on("cancel", finish);

    tour.addStep({
      id: "new-session",
      title: "Start here",
      text: "Each session locks onto one topic — upload material or just start asking questions, and Sensei figures out the scope.",
      attachTo: { element: "#dashboard-new-session", on: "bottom" },
      buttons: [{ text: "Next", action: tour.next }],
    });

    tour.addStep({
      id: "socratic",
      title: "Guided, not handed to you",
      text: "Instead of answers, Sensei asks Socratic questions that pull the reasoning out of you — grounded in whatever you uploaded.",
      buttons: [
        { text: "Back", classes: "shepherd-button-secondary", action: tour.back },
        { text: "Next", action: tour.next },
      ],
    });

    tour.addStep({
      id: "test-me",
      title: "Test yourself",
      text: "Open Test Me inside any session to explain a concept back in your own words — Sensei scores it on the 7 C's.",
      buttons: [
        { text: "Back", classes: "shepherd-button-secondary", action: tour.back },
        { text: "Got it", action: tour.complete },
      ],
    });

    tour.start();

    return () => {
      tour.hide();
    };
  }, [me, markOnboarded]);

  return null;
}
