import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import GradeChip from "@/components/GradeChip";
import { es } from "@/strings/es";

export default function Shell({ children }: { children: React.ReactNode }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-20 flex items-center justify-between border-b bg-background px-4 py-3">
        <button aria-label={es.nav.menu} onClick={() => setMenuOpen(true)} className="text-xl">
          ☰
        </button>
        <span className="font-bold">{es.appName}</span>
        {user?.role === "teacher" ? <span className="w-6" /> : <GradeChip />}
      </header>

      {menuOpen && (
        <div className="fixed inset-0 z-30 flex">
          <nav className="flex w-72 flex-col gap-1 border-r bg-background p-4">
            <p className="mb-2 font-bold">@{user?.username}</p>
            <Link to="/clases" className="rounded-md px-3 py-2 hover:bg-accent" onClick={() => setMenuOpen(false)}>
              {es.nav.classes}
            </Link>
            {user?.role === "teacher" && (
              <Link to="/revisar" className="rounded-md px-3 py-2 hover:bg-accent" onClick={() => setMenuOpen(false)}>
                {es.revisar.title}
              </Link>
            )}
            {user?.role === "teacher" && (
              <Link to="/configurar" className="rounded-md px-3 py-2 hover:bg-accent" onClick={() => setMenuOpen(false)}>
                {es.configurar.title}
              </Link>
            )}
            <button onClick={handleLogout} className="mt-auto rounded-md px-3 py-2 text-left text-destructive hover:bg-accent">
              {es.nav.logout}
            </button>
          </nav>
          <div className="flex-1 bg-black/40" onClick={() => setMenuOpen(false)} />
        </div>
      )}

      <main className="flex-1 pb-16">{children}</main>

      <nav className="fixed inset-x-0 bottom-0 z-20 flex items-center justify-around border-t bg-background py-2">
        <Link to="/" aria-label={es.nav.home} className="p-2 text-xl">
          🏠
        </Link>
        <Link to="/componer" aria-label={es.nav.create} className="p-2 text-xl">
          ➕
        </Link>
        <Link to="/onboarding" aria-label={es.nav.profile} className="p-2 text-xl">
          👤
        </Link>
      </nav>
    </div>
  );
}
