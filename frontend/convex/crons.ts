import { cronJobs } from "convex/server";
import { internal } from "./_generated/api";

const crons = cronJobs();

// ADR-0006: single hourly sweep finds sessions inactive 3+ days and tells
// FastAPI to delete their chunks + raw PDFs before flipping status:"expired".
crons.interval(
  "expire inactive sessions",
  { hours: 1 },
  internal.sessions_internal.cleanupExpiredSessions,
);

export default crons;
