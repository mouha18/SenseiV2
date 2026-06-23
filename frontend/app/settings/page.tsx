"use client";

import { useAuthActions, useAuthToken } from "@convex-dev/auth/react";
import { useMutation, useQuery } from "convex/react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { api } from "@/convex/_generated/api";
import { apiFetch, ApiError } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function SettingsPage() {
  const me = useQuery(api.users.getMe);
  const setGeminiKey = useMutation(api.users.setGeminiKey);
  const clearGeminiKey = useMutation(api.users.clearGeminiKey);
  const revokeSessions = useMutation(api.users.revokeSessions);
  const { signOut } = useAuthActions();
  const token = useAuthToken();
  const router = useRouter();

  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSaveKey(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const { key_ciphertext } = await apiFetch<{ key_ciphertext: string }>(
        "/keys/validate",
        {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
          body: JSON.stringify({ gemini_api_key: apiKey }),
        },
      );
      await setGeminiKey({ ciphertext: key_ciphertext });
      setApiKey("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this key.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRemoveKey() {
    await clearGeminiKey({});
  }

  async function handleLogout() {
    await revokeSessions({});
    await signOut();
    router.push("/login");
  }

  if (me === undefined) return null;

  return (
    <div className="flex flex-1 items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-4">
        <Link
          href="/dashboard"
          className="inline-block font-mono text-xs text-muted-foreground hover:text-foreground"
        >
          ← Dashboard
        </Link>
        <Card>
          <CardHeader>
            <CardTitle>Settings</CardTitle>
            <CardDescription>{me?.email}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {me?.hasGeminiKey ? (
              <div className="space-y-2">
                <p className="text-sm">
                  You&apos;re using your own Gemini API key. The Daily Allowance
                  does not apply.
                </p>
                <Button variant="outline" onClick={handleRemoveKey}>
                  Remove key
                </Button>
              </div>
            ) : (
              <form onSubmit={handleSaveKey} className="space-y-4">
                <p className="text-sm text-muted-foreground">
                  You&apos;re currently using Sensei&apos;s shared key, limited
                  to 20 questions per day. Adding your own Gemini key is
                  optional and removes that limit.
                </p>
                <div className="space-y-1.5">
                  <Label htmlFor="apiKey">Gemini API key (optional)</Label>
                  <Input
                    id="apiKey"
                    type="password"
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    required
                  />
                </div>
                {error && <p className="text-sm text-destructive">{error}</p>}
                <Button type="submit" disabled={submitting}>
                  Save key
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
        <Button variant="ghost" className="w-full" onClick={handleLogout}>
          Log out
        </Button>
      </div>
    </div>
  );
}
