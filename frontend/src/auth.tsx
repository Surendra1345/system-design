import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, ApiError, getToken, setToken } from "./api";
import type { Catalog, Progress } from "./types";

interface AuthValue {
  progress: Progress | null;
  loggedIn: boolean;
  ready: boolean;
  catalog: Catalog | null;
  aiEnabled: boolean;
  refresh: () => Promise<void>;
  login: (u: string, p: string) => Promise<void>;
  register: (u: string, p: string) => Promise<void>;
  logout: () => Promise<void>;
  isDone: (lessonId: string) => boolean;
}

const Ctx = createContext<AuthValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [progress, setProgress] = useState<Progress | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [aiEnabled, setAi] = useState(false);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    if (!getToken()) { setProgress(null); return; }
    try { setProgress(await api<Progress>("GET", "/api/progress")); }
    catch (e) { if (e instanceof ApiError && e.status === 401) { setToken(null); setProgress(null); } }
  }, []);

  useEffect(() => {
    Promise.all([
      api<Catalog>("GET", "/api/catalog").then(setCatalog),
      api<{ enabled: boolean }>("GET", "/api/ai/status").then(r => setAi(r.enabled)).catch(() => setAi(false)),
      refresh(),
    ]).finally(() => setReady(true));
  }, [refresh]);

  const start = useCallback(async (path: string, u: string, p: string) => {
    const r = await api<{ token: string }>("POST", path, { username: u, password: p });
    setToken(r.token);
    await refresh();
  }, [refresh]);

  const value = useMemo<AuthValue>(() => ({
    progress, catalog, aiEnabled, ready, refresh,
    loggedIn: progress !== null,
    login: (u, p) => start("/api/auth/login", u, p),
    register: (u, p) => start("/api/auth/register", u, p),
    logout: async () => { try { await api("POST", "/api/auth/logout", {}); } catch { /* already gone */ } setToken(null); setProgress(null); },
    isDone: id => { const l = progress?.lessons[id]; return !!l && (l.stars > 0 || l.read); },
  }), [progress, catalog, aiEnabled, ready, refresh, start]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthValue {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside AuthProvider");
  return v;
}
