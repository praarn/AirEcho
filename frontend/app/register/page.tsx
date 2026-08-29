"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { Logo } from "@/components/Nav";
import { Spinner } from "@/components/ui";

export default function RegisterPage() {
  const { register, user } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // already signed in — skip straight to the dashboard
  useEffect(() => {
    if (user) router.replace("/dashboard");
  }, [user, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 8) {
      setErr("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await register(email, password);
    } catch (e) {
      setErr(e instanceof ApiError ? String(e.detail) : "Registration failed");
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <Link href="/" className="mb-8 flex justify-center">
          <Logo className="text-lg" />
        </Link>
        <div className="card">
          <h1 className="text-lg font-semibold text-white">Create your account</h1>
          <p className="mt-1 text-sm text-slate-500">
            Your health data is isolated per user and exportable/deletable at any time.
          </p>
          <form onSubmit={submit} className="mt-5 space-y-3">
            <input
              className="input"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <input
              className="input"
              type="password"
              placeholder="Password (8+ characters)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            {err && <p className="text-sm text-aq-bad">{err}</p>}
            <button className="btn-primary w-full" disabled={busy}>
              {busy ? <Spinner /> : "Create account"}
            </button>
          </form>
        </div>
        <p className="mt-4 text-center text-sm text-slate-500">
          Already have an account?{" "}
          <Link href="/login" className="text-brand hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
