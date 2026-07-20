import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { es } from "@/strings/es";
import type { AuthResponse } from "@/lib/types";

declare global {
  interface Window {
    google?: any;
  }
}

export default function Login() {
  const buttonRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState(false);
  const navigate = useNavigate();
  const { refresh } = useAuth();

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
            await refresh();
            navigate(auth.needs_onboarding ? "/onboarding" : "/", { replace: true });
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
  }, [navigate, refresh]);

  return (
    <main className="flex min-h-dvh flex-col items-center justify-center gap-6 p-6">
      <h1 className="text-2xl font-bold">{es.login.title}</h1>
      <p className="text-muted-foreground">{es.login.subtitle}</p>
      <div ref={buttonRef} />
      {error && <p className="text-destructive">{es.login.error}</p>}
    </main>
  );
}
