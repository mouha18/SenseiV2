import Link from "next/link";

const STEPS = [
  {
    label: "01 / UPLOAD",
    body: "Drop PDFs. Sensei extracts the scope and stays on topic.",
  },
  {
    label: "02 / BE ASKED",
    body: "Socratic prompts pull the reasoning out of you.",
  },
  {
    label: "03 / TEST ME",
    body: "Explain it back. Get scored on the 7 C's.",
  },
];

export default function Home() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between px-10 py-7">
        <div className="flex items-center gap-2.5">
          <span className="inline-block h-[11px] w-[11px] bg-primary" />
          <span className="font-sans text-base font-semibold tracking-tight">
            Sensei
          </span>
        </div>
        <Link
          href="/login"
          className="font-sans text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          Log in
        </Link>
      </header>

      <main className="mx-auto flex w-full max-w-[920px] flex-1 flex-col justify-center px-10 pb-28">
        <div className="font-mono text-[11px] font-medium uppercase tracking-[.22em] text-primary">
          Socratic study tool
        </div>
        <h1 className="mt-5 max-w-[15ch] font-sans text-[clamp(38px,6vw,70px)] font-medium leading-[1.04] tracking-[-.025em] text-balance">
          It doesn&apos;t hand you answers. It asks better questions.
        </h1>
        <p className="mt-7 max-w-[54ch] font-sans text-lg leading-[1.65] text-muted-foreground text-pretty">
          Sensei reads your material, locks onto the topic, and guides you
          with Socratic prompts — then tests whether you can actually
          explain it back.
        </p>

        <div className="mt-10 flex flex-wrap gap-3">
          <Link
            href="/signup"
            className="inline-flex items-center gap-2 bg-primary px-6 py-3.5 font-sans text-[15px] font-medium text-primary-foreground hover:bg-primary/80"
          >
            Get started
          </Link>
          <Link
            href="/login"
            className="inline-flex items-center gap-2 border border-border px-6 py-3.5 font-sans text-[15px] font-medium text-foreground hover:border-muted-foreground"
          >
            See a demo session →
          </Link>
        </div>

        <div className="mt-20 flex flex-wrap gap-12">
          {STEPS.map((step) => (
            <div key={step.label} className="flex max-w-[200px] flex-col gap-2">
              <span className="font-mono text-[11px] font-medium tracking-[.16em] text-primary">
                {step.label}
              </span>
              <span className="font-sans text-sm leading-[1.55] text-muted-foreground">
                {step.body}
              </span>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
