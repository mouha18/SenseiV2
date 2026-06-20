import Link from "next/link";
import { AuthForm } from "@/components/auth/AuthForm";

export default function LoginPage() {
  return (
    <div className="flex flex-1 items-center justify-center p-4">
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
  );
}
