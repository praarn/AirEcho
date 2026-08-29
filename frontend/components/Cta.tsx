"use client";

import Link from "next/link";
import { useAuth } from "@/lib/auth";

/** Render children only when NOT signed in. */
export function SignedOut({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  if (loading || user) return null;
  return <>{children}</>;
}

/** Render children only when signed in. */
export function SignedIn({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user) return null;
  return <>{children}</>;
}

/**
 * Primary call-to-action row for marketing pages. Signed-in visitors get a
 * dashboard link instead of "Create an account" / "Sign in" all over again.
 */
export function HeroCtas() {
  const { user, loading } = useAuth();

  if (user) {
    return (
      <>
        <Link href="/dashboard" className="btn-primary">
          Open dashboard
        </Link>
        <Link href="/guide" className="btn-ghost">
          Read the guide
        </Link>
      </>
    );
  }

  return (
    <>
      <Link
        href="/register"
        className="btn-primary"
        aria-disabled={loading}
        tabIndex={loading ? -1 : undefined}
      >
        Create an account
      </Link>
      <Link href="/login" className="btn-ghost">
        Sign in
      </Link>
      <Link href="/guide" className="btn-ghost">
        Read the guide
      </Link>
    </>
  );
}

/** Footer link that points signed-in users at the dashboard, others at sign-in. */
export function FooterAuthLink({ className }: { className?: string }) {
  const { user } = useAuth();
  return (
    <Link href={user ? "/dashboard" : "/login"} className={className}>
      {user ? "Dashboard" : "Sign in"}
    </Link>
  );
}
