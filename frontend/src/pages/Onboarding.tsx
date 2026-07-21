import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { es } from "@/strings/es";
import type { User } from "@/lib/types";

const USERNAME_RE = /^[a-z0-9_]{3,20}$/;

export default function Onboarding() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: { pathname: string; search: string } } | null)?.from;
  const redirectTarget = from ? `${from.pathname}${from.search}` : "/";
  const [username, setUsername] = useState("");
  const [bio, setBio] = useState("");
  const [available, setAvailable] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (user?.username) navigate(redirectTarget, { replace: true });
  }, [user, navigate, redirectTarget]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- resets stale availability state before the debounced re-check kicks off, not a cascading-render risk
    setAvailable(null);
    if (!USERNAME_RE.test(username)) return;
    let cancelled = false;
    const t = setTimeout(async () => {
      const res = await api<{ available: boolean }>(
        `/api/users/username-available?u=${encodeURIComponent(username)}`,
      );
      if (!cancelled) setAvailable(res.available);
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [username]);

  const valid = USERNAME_RE.test(username) && available !== false;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setSaving(true);
    setError(null);
    try {
      await api<User>("/api/users/me", {
        method: "PATCH",
        body: JSON.stringify({ username, bio }),
      });
      await refresh();
      navigate(redirectTarget, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError && err.status === 409 ? es.onboarding.usernameTaken : es.onboarding.genericError);
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-4 p-6">
      <h1 className="text-2xl font-bold">{es.onboarding.title}</h1>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1">
          <span className="font-medium">{es.onboarding.usernameLabel}</span>
          <input
            className="rounded-md border px-3 py-2"
            value={username}
            onChange={(e) => setUsername(e.target.value.toLowerCase())}
            autoFocus
          />
          <span className="text-sm text-muted-foreground">{es.onboarding.usernameHint}</span>
          {available === false && (
            <span className="text-sm text-destructive">{es.onboarding.usernameTaken}</span>
          )}
        </label>
        <label className="flex flex-col gap-1">
          <span className="font-medium">{es.onboarding.bioLabel}</span>
          <textarea
            className="min-h-24 rounded-md border px-3 py-2"
            placeholder={es.onboarding.bioPlaceholder}
            value={bio}
            onChange={(e) => setBio(e.target.value)}
            maxLength={500}
          />
        </label>
        {error && <p className="text-destructive">{error}</p>}
        <button
          type="submit"
          disabled={!valid || saving}
          className="rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground disabled:opacity-50"
        >
          {es.onboarding.submit}
        </button>
      </form>
    </main>
  );
}
