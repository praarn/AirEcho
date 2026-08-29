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

const REPO_URL = "https://github.com/praarn/AirEcho";

function GitHubLink({ className }: { className?: string }) {
  return (
    <a
      href={REPO_URL}
      target="_blank"
      rel="noreferrer"
      aria-label="View source on GitHub"
      className={clsx(
        "rounded-lg p-1.5 text-slate-400 transition hover:bg-white/[0.06] hover:text-slate-100",
        className,
      )}
    >
      <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
        <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8Z" />
      </svg>
    </a>
  );
}

export function Nav() {
  const { user, logout } = useAuth();
  const path = usePathname();
  const links = user
    ? [
        { href: "/dashboard", label: "Dashboard" },
        { href: "/admin", label: "Live feed" },
        { href: "/guide", label: "Guide" },
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
          {!user && (
            <>
              <a
                href="#about"
                className="hidden rounded-lg px-3 py-1.5 text-sm text-slate-400 transition hover:text-slate-100 sm:inline-block"
              >
                About
              </a>
              <Link
                href="/guide"
                className={clsx(
                  "hidden rounded-lg px-3 py-1.5 text-sm transition sm:inline-block",
                  path === "/guide"
                    ? "bg-white/[0.06] text-white"
                    : "text-slate-400 hover:text-slate-100",
                )}
              >
                Guide
              </Link>
              <GitHubLink className="mx-1" />
              <Link href="/login" className="btn-ghost !px-3 !py-1.5 text-xs">
                Sign in
              </Link>
            </>
          )}
          {user && (
            <div className="ml-2 flex items-center gap-3 border-l border-white/10 pl-3">
              <GitHubLink />
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
