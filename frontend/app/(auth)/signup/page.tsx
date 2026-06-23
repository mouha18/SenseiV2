import Link from "next/link";
import { AuthForm } from "@/components/auth/AuthForm";

export default function SignupPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="px-10 py-7">
        <Link href="/" className="inline-flex items-center gap-2.5">
          <span className="inline-block h-[11px] w-[11px] bg-primary" />
          <span className="font-sans text-base font-semibold text-foreground">Sensei</span>
        </Link>
      </header>
      <div className="flex flex-1 items-center justify-center p-4 pb-20">
        <div className="space-y-4">
          <AuthForm
            flow="signUp"
            title="Create your Sensei account"
            description="Start studying with a Socratic tutor grounded in your own materials."
          />
          <p className="text-center text-sm text-muted-foreground">
            Already have an account?{" "}
            <Link href="/login" className="underline">
              Log in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
