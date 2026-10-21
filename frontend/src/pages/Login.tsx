import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, setToken } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { queryClient } from "@/lib/query";
import { es } from "@/strings/es";
import type { AuthResponse } from "@/lib/types";

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: { credential: string }) => void;
          }) => void;
          renderButton: (
            parent: HTMLElement,
            options: { theme: string; size: string },
          ) => void;
        };
      };
    };
  }
}

export default function Login() {
  const buttonRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState(false);
  const navigate = useNavigate();
  const { refresh } = useAuth();
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string; search: string } } | null)?.from;

  useEffect(() => {
    let cancelled = false;
    async function init() {
      const { google_client_id } = await api<{ google_client_id: string }>("/api/config");
      const google = window.google;
      if (cancelled || !google || !buttonRef.current) return;
      google.accounts.id.initialize({
        client_id: google_client_id,
        callback: async (response: { credential: string }) => {
          try {
            const auth = await api<AuthResponse>("/api/auth/google", {
              method: "POST",
              body: JSON.stringify({ credential: response.credential }),
            });
            setToken(auth.token);
            // A session can end without an explicit logout (expired token, a
            // second account): drop whatever the previous one cached so its
            // grades and teacher-only data never reach this account.
            queryClient.clear();
            await refresh();
            if (auth.needs_onboarding) {
              navigate("/onboarding", { replace: true, state: from ? { from } : undefined });
            } else {
              navigate(from ? `${from.pathname}${from.search}` : "/", { replace: true });
            }
          } catch {
            setError(true);
          }
        },
      });
      google.accounts.id.renderButton(buttonRef.current, { theme: "outline", size: "large" });
    }
    void init();
    return () => {
      cancelled = true;
    };
  }, [navigate, refresh, from]);

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-6 p-6">
      <h1 className="text-2xl font-bold">{es.login.title}</h1>
      <p className="text-muted-foreground">{es.login.subtitle}</p>
      <div ref={buttonRef} />
      {error && <p className="text-destructive">{es.login.error}</p>}
    </main>
  );
}
