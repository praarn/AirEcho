"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, clearTokens, getAccess, setTokens } from "./api";
import type { TokenPair, UserOut } from "./types";

interface AuthCtx {
  user: UserOut | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserOut | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const refreshMe = useCallback(async () => {
    if (!getAccess()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await apiFetch<UserOut>("/auth/me"));
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshMe();
  }, [refreshMe]);

  const login = useCallback(
    async (email: string, password: string) => {
      const t = await apiFetch<TokenPair>(
        "/auth/login",
        { method: "POST", body: JSON.stringify({ email, password }) },
        { auth: false },
      );
      setTokens(t);
      await refreshMe();
      router.push("/dashboard");
    },
    [refreshMe, router],
  );

  const register = useCallback(
    async (email: string, password: string) => {
      await apiFetch("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }, { auth: false });
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(() => {
    apiFetch("/auth/logout", { method: "POST" }).catch(() => {});
    clearTokens();
    setUser(null);
    router.push("/login");
  }, [router]);

  const value = useMemo(
    () => ({ user, loading, login, register, logout }),
    [user, loading, login, register, logout],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth must be used within AuthProvider");
  return c;
}
