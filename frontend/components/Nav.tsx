"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { clsx } from "@/lib/clsx";

export function Logo({ className }: { className?: string }) {
  return (
    <span className={clsx("flex items-center gap-2 font-semibold tracking-tight", className)}>
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden>
        <path
          d="M4 15c0-3 2-5 5-5 1-3 4-5 7-4s5 4 4 7c2 1 3 3 2 5"
          stroke="url(#g)"
          strokeWidth="1.8"
          strokeLinecap="round"
        />
        <circle cx="8" cy="18" r="1.6" fill="#38bdf8" />
        <circle cx="14" cy="19" r="1.6" fill="#7dd3fc" />
        <defs>
          <linearGradient id="g" x1="4" y1="6" x2="22" y2="20">
            <stop stopColor="#38bdf8" />
            <stop offset="1" stopColor="#a855f7" />
          </linearGradient>
        </defs>
      </svg>
      <span>
        Air<span className="text-brand">Echo</span>
      </span>
    </span>
  );
}

export function Nav() {
  const { user, logout } = useAuth();
  const path = usePathname();
  const links = user
    ? [
        { href: "/dashboard", label: "Dashboard" },
        { href: "/admin", label: "Live feed" },
      ]
    : [];

  return (
    <header className="sticky top-0 z-40 border-b border-white/5 bg-ink-950/70 backdrop-blur-lg">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link href={user ? "/dashboard" : "/"}>
          <Logo />
        </Link>
        <nav className="flex items-center gap-1">
          {links.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={clsx(
                "rounded-lg px-3 py-1.5 text-sm transition",
                path === l.href
                  ? "bg-white/[0.06] text-white"
                  : "text-slate-400 hover:text-slate-100",
              )}
            >
              {l.label}
            </Link>
          ))}
          {user && (
            <div className="ml-2 flex items-center gap-3 border-l border-white/10 pl-3">
              <span className="hidden text-xs text-slate-500 sm:inline">{user.email}</span>
              <button onClick={logout} className="btn-ghost !px-3 !py-1.5 text-xs">
                Sign out
              </button>
            </div>
          )}
        </nav>
      </div>
    </header>
  );
}
