"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { ApiError } from "@/lib/api";
import { Logo } from "@/components/Nav";
import { Spinner } from "@/components/ui";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("demo@example.com");
  const [password, setPassword] = useState("demo-pass-123");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      await login(email, password);
    } catch (e) {
      setErr(e instanceof ApiError ? String(e.detail) : "Sign in failed");
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
          <h1 className="text-lg font-semibold text-white">Welcome back</h1>
          <p className="mt-1 text-sm text-slate-500">Sign in to your dashboard.</p>
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
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            {err && <p className="text-sm text-aq-bad">{err}</p>}
            <button className="btn-primary w-full" disabled={busy}>
              {busy ? <Spinner /> : "Sign in"}
            </button>
          </form>
        </div>
        <p className="mt-4 text-center text-sm text-slate-500">
          No account?{" "}
          <Link href="/register" className="text-brand hover:underline">
            Create one
          </Link>
        </p>
      </div>
    </div>
  );
}
