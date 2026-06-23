import Link from "next/link";
import { AuthForm } from "@/components/auth/AuthForm";

export default function LoginPage() {
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
            flow="signIn"
            title="Log in to Sensei"
            description="Welcome back. Enter your credentials to continue."
          />
          <p className="text-center text-sm text-muted-foreground">
            Don&apos;t have an account?{" "}
            <Link href="/signup" className="underline">
              Sign up
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
